# Toolchain issues, with minimal repros

Found while bringing up the Arty A7 flow (2026-11-12). Not reported upstream (user
decision); each one is recorded here with its smallest reproducing input under
`upstream/<issue>/`. Every repro below was rerun on 2026-11-12 and reproduces.

Versions (pinned by `flake.lock`):

| tool | version | source |
|---|---|---|
| yosys | 0.70 (Release) | nixpkgs 02c087f (through the `wiz` input) |
| nextpnr (`nextpnr-xilinx`, himbaechel xilinx) | 1.0.0 | openXC7/nextpnr cf5f7a2, via openXC7/toolchain-nix 22327eb |
| Project X-Ray (`xc7frames2bit`, `fasm2frames`) | 0.9.2 | openXC7/prjxray 54fea88, via toolchain-nix 22327eb |
| chip database | xc7a50t (used for xc7a35t) | `nix/chipdb.nix` from that nextpnr and prjxray-db |

Run everything in `nix develop`, from the issue's directory. `$ARTY_CHIPDB` and
`$PRJXRAY_DB_DIR` come from the devShell. Generated files are git-ignored.

## 1. yosys synth_xilinx: a register copied into a DSP leaves its fabric twin with INIT x

**Input:** `upstream/yosys-dsp-init/top.v` (13 lines). A shift register `sh` that starts
at zero and has a clock enable feeds a registered multiply (`pr <= sh * sh`) and an
output pin.

```sh
yosys -q -p "read_verilog top.v; synth_xilinx -flatten -abc9 -arch xc7 -top top; write_verilog -noattr top_syn.v"
grep -E "\.(AREG|BREG|MREG)\(|INIT\(1'h" top_syn.v | sort | uniq -c
```

**Observed:** `AREG=1`, `BREG=1`, `MREG=1`, and all 8 FDREs that still drive `q` have
`.INIT(1'hx)`.

**Expected:** `.INIT(1'h0)`, the register's initial value. With `-nodsp` the flip-flops
keep `INIT(1'h0)`.

Notes:
- With a non-zero initial value (`8'hA5`), yosys does not absorb the register and keeps
  the INITs.
- With a synchronous set (FDSE), the INITs are kept too.
- So in the cases seen, the lost value was 0 on an FDRE. nextpnr writes an x-init FDRE
  with 0, so the bitstream is right, but simulating the synthesised netlist with
  yosys's cell models gives x (our `squares` design failed post-synthesis simulation
  this way).

**Workaround:** before post-synthesis simulation, the `arty` driver replaces
`INIT(1'hx)` on FDRE/FDCE with 0 and on FDSE/FDPE with 1 (what nextpnr does in the
bitstream), and reports how many it changed.

## 2. nextpnr-xilinx: core dump on Digilent's `[get_ports { clk }]`; `create_clock` options ignored

**Input:** `upstream/nextpnr-xdc-braces/`: `top.v` (a switch to an LED, one flip-flop),
`spaces.xdc` (Digilent's master-XDC spelling, spaces inside the braces) and
`nospaces.xdc` (the same without the spaces).

```sh
yosys -q -p "read_verilog top.v; synth_xilinx -flatten -abc9 -arch xc7 -top top; write_json top.json"
nextpnr-xilinx --chipdb $ARTY_CHIPDB/xc7a35tcsg324.bin --xdc spaces.xdc   --json top.json --fasm spaces.fasm   --log spaces.log -q
nextpnr-xilinx --chipdb $ARTY_CHIPDB/xc7a35tcsg324.bin --xdc nospaces.xdc --json top.json --fasm nospaces.fasm --log nospaces.log -q
```

**Observed:**
- With `spaces.xdc`: `Assertion failure: str.back() == '}' (himbaechel/uarch/xilinx/xdc.cc:55)`, abort, core dump (exit 134). The target `[get_ports { clk }]` is split at spaces before its braces are stripped, and the lone `{` reaches `strip_quotes`.
- With `nospaces.xdc`: it runs (exit 0), but warns `ignoring unsupported XDC option '-add'`, `'-name'` and `'-waveform'` on Digilent's `create_clock -add -name sys_clk_pin -period 10.00 -waveform {0 5}`. The timing report then names the clock after a net (`$abc$…$aiger$o…`).

**Expected:** Digilent's own spelling is accepted (Vivado takes it). Without support for
the options, the clock is at least named `-name`'s value.

**Workaround:** `Xdc.emit` (Wiz `lib/Hdl/Xdc.wiz`) writes `[get_ports {clk}]` and plain
`create_clock -period P [get_ports {clk}]`.

## 3. xc7frames2bit: an empty frames file gives a 2.2 MB "bitstream" and exit 0

**Input:** none, just an empty file.

```sh
: > empty.frames
xc7frames2bit --part_file $PRJXRAY_DB_DIR/artix7/xc7a35tcsg324-1/part.yaml --part_name xc7a35tcsg324-1 \
  --frm_file empty.frames --output_file empty.bit; echo "exit $?"; ls -l empty.bit
```

**Observed:** exit 0 and a 2192115-byte `empty.bit`, a full-size configuration with
nothing in it. We hit this when fasm2frames failed (a missing Python module), its empty
output went on to xc7frames2bit, and the "bitstream" looked fine.

**Expected:** an error for an empty (or truncated) frames file, or at least a warning.

**Workaround:** the `arty` driver stops when fasm2frames fails, and writes the frames
file only from its output.

## 4. nextpnr-xilinx: fractured LUT pairs list each other's pins, so the SDF has false loops

**Input:** `upstream/nextpnr-sdf-lut-pins/`: `top.v` (the `echo` design, a UART echo,
78 lines of Verilog as Wiz emits it), `top.xdc`, and `check.py`, which compares the SDF
with the routed netlist and looks for loops.

```sh
yosys -q -p "read_verilog top.v; synth_xilinx -flatten -abc9 -arch xc7 -top top; write_json top.json"
nextpnr-xilinx --chipdb $ARTY_CHIPDB/xc7a35tcsg324.bin --xdc top.xdc --json top.json --fasm top.fasm \
  --write routed.json --sdf top.sdf --log top.log -q
python3 check.py routed.json top.sdf
```

**Observed:**

```
SDF interconnects between cells: 630; not in the routed netlist: 0
LUTs listing their own output as an input: 1
   $abc$22325$lut$aiger22324$170 pin A4 (SLICE_X1Y59/B6LUT INIT=8 bits)
```

The cell is a LUT3 (8-bit INIT; in the synthesised netlist it has three inputs). After
packing it shares site B with a LUT5 (`B5LUT`) that reads the LUT3's output through the
shared pin A4. The routed netlist gives both cells all six pins of the site, the
LUT3's own output among them. The SDF then has a timing arc A4 → O6 on the LUT3, a
combinational loop the design doesn't have.

In the RISC-V core of the wiz-rv agent (a bigger design, not committed), the same
check finds 22 such LUTs and one pair of LUTs that list each other's outputs
(`SLICE_X1Y97/A6LUT` and `SLICE_X1Y100/A6LUT`, both LUT2). The synthesised netlist has
no such connection. That made our longest-path search over the SDF see a two-LUT loop.

**Expected:** each LUT cell lists (and the SDF times) only the pins its own function
uses, so the site's shared pins don't create arcs from a LUT's output back to itself.

**Workaround:** our longest-path search (`scripts/sdfpath.py`) skips edges that close a
cycle, which gives a bound that errs on the long side.

Untested: whether nextpnr's own timing analysis follows the same arcs. Its reports
looked plausible, and the bitstreams work on the board.
