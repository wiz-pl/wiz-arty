# Findings: Wiz's HDL on the Arty A7 with openXC7

From porting the iCEstick designs to a Digilent Arty A7-35T (2026-11-12, Wiz branch
`agent/artix-target`, stacked on #166).

## On the board (Arty A7-35T, xc7a35ticsg324-1L)

Loaded into SRAM with `openFPGALoader -b arty_a7_35t --busdev-num BUS:DEV` (nothing
written to flash). `--ftdi-serial` failed with libftdi error -9 ("unable to fetch serial
number") while the iCEstick's FT2232 was on the same bus; `--busdev-num` works. JTAG
reads IDCODE 0x0362D093 (xc7a35t).

| design | check | result |
|---|---|---|
| `blinky` | LEDs looked at by the user; UART for 2 s | LD4-LD7 count in binary as expected; UART silent |
| `hello` | UART read for 3 s | 136 bytes: 8 × `Hello from Wiz!\r\n`, nothing else |
| `echo` | 23-byte string; all 256 byte values in one burst | identical |
| `echo` (divider 868) | 4096 random bytes back to back, 3 runs | one byte dropped each time, near byte 2223 (see below) |
| `squares` | 10 bytes; then all 256 values twice | replies exactly as specified: RAMB18E1 and DSP48E1 work |
| `echo` (divider 866) | 4096 random bytes ×3, then 32768 in one burst | all identical |
| `sq36`, `rom36` (bisect) | `squares` on a RAMB36E1; a hello read from a RAMB36E1 ROM (INIT) | both as specified |
| `half_hello` (bisect) | hello behind a free-running half-rate enable, divider 433 | repeated text |
| wiz-rv `rv32im_arty_uart` | RV32IM core (Verilog from the wiz-rv agent): 4 RAMB36E1, 10 DSP48E1, 12 RAM32M, half rate | banner, `M self-test: PASS`, primes to 997, `> ` prompt that echoes: byte for byte as specified |

**A host-side trap (cost an hour):** `stty … min 0 time 5` makes `cat` give up after
0.5 s without data, so a capture started before a load ends during the 2-3 s
configuration and sees nothing. Several "silent" designs (the RISC-V core, the half-rate
hello) were in fact working. Capture with `min 1 time 0` and a `timeout`.

## UART clock rates: the board must be fast of the FT2232, not exact

An FT2232 divides 3 MHz by an integer: "115200" is 3 MHz / 26 = 115384.6 baud
(+0.16 %). The Arty's first divider, 868 (100 MHz / 115200 rounded, 115207.4 baud), is
slower than that. `echo` holds one byte, so in a long burst it falls behind by about
0.015 bit per byte and drops a byte after about 2200 (seen on the board, three times out
of three). The iCEstick's 12 MHz / 104 = 115384.6 baud is exactly the FT2232's rate,
which is why it never showed there. Now the divider is computed from the FT2232's rate,
rounded down (866: 115473.4 baud, +0.08 % of the host), and the simulations model the
host at 2600/3 cycles per bit. This is a property of any design that relays at line rate
with bounded buffering. The rounded-to-nominal divider is the wrong default for it.

## The toolchain: openXC7 from Nix

* `github:openXC7/toolchain-nix` (pinned in flake.lock) builds from source. None of it
  is in cache.nixos.org or the configured caches. The first build compiles nextpnr (the
  himbaechel `xilinx` architecture, plus a shim `nextpnr-xilinx` that translates the old
  flags), Project X-Ray 0.9.2 and fasm, and fetches prjxray-db. It took about 20 minutes
  here.
* Its `nextpnr-xilinx-chipdb.artix7` builds every Artix-7 die, xc7a200t included.
  `nix/chipdb.nix` builds only the two an Arty can carry (xc7a50t, which nextpnr uses for
  the xc7a35t, and xc7a100t), with the same recipe.
* `fpga-assembler` (Bazel, a nested `builtins.getFlake`) is not needed: `fasm2frames` and
  `xc7frames2bit` from prjxray do the job.
* fasm2frames is a Python script on openXC7's Python 3.12. It needs fasm (whose parser is
  a Cython/C++ extension, hence `cython` for `pyximport`), prjxray's modules, pyyaml,
  simplejson, intervaltree and textx on `PYTHONPATH`. The devShell takes those from
  openXC7's own nixpkgs (Wiz's has another Python).
* **xc7frames2bit turns an empty frames file into a 2.2 MB "bitstream"** without a
  word. The driver stops when fasm2frames fails, so it can't happen there, but it is a
  trap in hand-written flows.
* Prjxray-db has no `-1L`/`i` parts. The xc7a35ticsg324-1L is built as
  xc7a35tcsg324-1, the same die and bitstream.
* No F4PGA or Vivado here. Both would take the same Verilog and XDC (README).

## nextpnr-xilinx and XDC

* **nextpnr-xilinx cannot read Digilent's own XDC spelling.** `[get_ports { clk }]`
  (spaces inside the braces, as in every Digilent master XDC) aborts nextpnr with an
  assertion (`str.back() == '}'`, `xdc.cc:55`) and a core dump: the target is split at the
  spaces before the braces are stripped. `{clk}` works, and `Xdc.emit` writes that.
* `create_clock -name` is ignored with a warning, while `-period` is honoured. The timing
  report then names the clock after a net (`$abc$…$aiger$o10`, or the BRAM's clock pin)
  instead of `clk`.
* One-bit ports are emitted `[0:0]`: nextpnr calls them `uart_tx` (and retries `x[0]`
  as `x`), Vivado `uart_tx[0]`.

## Inference (yosys 0.70, synth_xilinx)

* HDL RAMs map to block RAM with no help: 1024x16 to a RAMB18E1, 2048x16 to a RAMB36E1.
  The read register is absorbed, even with an enable.
* **ROMs do not.** A registered 1024x8 ROM became 160 LUT6s and 63 MUXF7/8. With
  `(* rom_style = "block" *)` it is one RAMB18E1, so `Verilog.emit` now marks
  never-written memories of 4 Kbit or more. iCE40 maps the ROM to block RAM either way.
* `Hw.mul` maps to DSP48E1 on its own: 16x16 to 1, 32x32 to 3. The output register is
  absorbed.
* **yosys's DSP register absorption drops `init`.** In `squares` the receiver's shift
  register also feeds the multiplier. xilinx_dsp copied it into the DSP's A/B registers
  and left the fabric copy's eight FDREs with `INIT x` (none with `-nodsp`). In the
  bitstream nextpnr gives an x-init flip-flop its primitive's default (FDRE/FDCE 0,
  FDSE/FDPE 1), which matched the design's 0 here, and the board agrees. The Xilinx cell
  models say x, so post-synthesis simulation failed (`led = xxxx`). The driver now gives
  those flip-flops the same default before postsim and reports how many there were.
  That got past the DSP. The next x comes from the block RAM: **yosys's RAMB18E1/RAMB36E1
  in `xilinx/cells_sim.v` is a black box** (parameters and timing arcs, no behaviour), so
  no design with block RAM can be simulated after synthesis with yosys's library. The
  driver skips postsim for those, and says so. `squares` is checked on the board instead
  (Vivado's unisims would do it). A
  register with a non-default initial value in front of a multiplier would be wrong in
  hardware. That is worth an upstream report to yosys.
* Utilisation and timing (35T and 100T, yosys `stat`, nextpnr): all four designs pass at
  100 MHz with Fmax 260-420 MHz; `squares` is 1 RAMB18E1 + 1 DSP48E1 + 57 FFs + ~32
  LUTs.

## Timing checks beyond nextpnr's report

nextpnr reports the worst path per clock and takes `set_multicycle_path` only by
destination cell, so a half-rate design (2-cycle paths everywhere except from the
enable flip-flop) cannot be checked with one constraint. What worked: constrain the clock
at the half rate (20 ns), then bound the 1-cycle paths from the enable flip-flop with a
longest-path search over nextpnr's `--sdf` output (`scripts/sdfpath.py FILE.sdf
FF_CELL`: about 6.5 ns, under 10 ns). nextpnr's SDF attributes some pins of fractured LUT
pairs (O5/O6 of one site) to the wrong LUT, which shows up as a fake two-LUT loop. That is
worth an upstream report. A `-nobram` build of the core (512 RAM256X1S) misses 50 MHz
(48 MHz).

## Wiz

* **Value simulation of a RAM was quadratic in its length.** `HwTy.El.memWrite` wrapped
  the memory in a new closure every cycle, enabled or not, so a read cost the number of
  cycles so far. `squares` (97k cycles) did not finish in 5 minutes. A disabled write is
  now the memory itself (`Hdl.memWr`, now in #166). After that, `arty gen` (value and
  netlist simulation of the four designs, 415k cycles in all) takes about 20 s.
* `grail test` has a fixed 60 s limit. The UART tests therefore run with 16 cycles per
  bit, the same circuits with other constants, and `arty gen` runs them at the board's
  divider.
* Pin tables: iCE40's `Pin` takes numbers, Xilinx pins are names (`E3`), so `Hdl.Xdc` has
  its own `XPin`. The board table lists the whole board and `Xdc.check` ignores unused
  resources. `Pcf.check` instead treats a pin for no port as an error, which makes a
  whole-board table impossible there.

## The PmodOLEDrgb designs (branch `oled`)

* **Porting from the iCEstick was copying.** The SSD1331 controller, the effects, the
  ray tracers and the SSD1331 model (wiz-icestick-uart, branch `oled-demo`, written for
  wiz b6ad475) went over with the module names changed. Two things were new: the board
  wrapper (`Circuit.slow`: one cycle in eight behind a clock-enable flip-flop, and the
  OLED's pins as one port put on a Pmod header by `OledArty.board`), and per-design XDC
  files in the driver (the UART designs shared one).
* **wiz ada3a919 cannot infer the record in `S.pack (S.mk …)` here** (it could at
  b6ad475): in the controllers' output functions, with nine fields some of which are
  projections of a nested bundle, `RgbBoard.pack (RgbBoard.mk hi … p.pmoden)` fails with
  "type mismatch: expected ?m r inst c cs …, inferred (hi, …, fun fields => ())
  (spine length mismatch)". A small repro with plain arguments elaborates. Writing the
  type, `let b : RgbBoard r := RgbBoard.mk …; RgbBoard.pack b`, works (`rgbOut`,
  `monoOut`).
* **The clock enable costs nothing in timing here:** `oled_test` routes at 202 MHz
  (constrained at 12.5 MHz, its enabled rate), so it would pass 100 MHz even as
  single-cycle paths.
