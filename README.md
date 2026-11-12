# wiz-arty

[Wiz](https://github.com/wiz-pl/wiz)'s hardware description library on a Digilent
Arty A7 (Artix-7), built with grail and the open openXC7 flow: the iCEstick designs of
[wiz-icestick-uart](../wiz-icestick-uart) (blinky, hello, echo) ported to the board, and
one more (`squares`) that uses block RAM and a DSP slice.

```
src/Arty/*.wiz ── grail build ──▶ .grail/bin/arty               (the flow driver, in Wiz)
                                     │ gen      Verilog, build/arty.xdc, test benches, traces
                                     │ sim      Icarus Verilog replays the traces
                                     │ bit      yosys synth_xilinx ▶ nextpnr-xilinx ▶ fasm2frames ▶ xc7frames2bit
                                     ▼ postsim  the same traces on the synthesised netlists
```

## The board

Digilent Arty A7: an Artix-7 in a CSG324 package, a 100 MHz oscillator, four green LEDs,
four RGB LEDs, four buttons, four switches, four Pmod headers and an FT2232H whose second
channel is a serial port. Two versions:

| board | device | Vivado part | open-flow part (X-Ray) | nextpnr database |
|---|---|---|---|---|
| Arty A7-35T (the default) | XC7A35T | xc7a35ticsg324-1L | xc7a35tcsg324-1 | xc7a50t's (same die) |
| Arty A7-100T | XC7A100T | xc7a100tcsg324-1 | xc7a100tcsg324-1 | xc7a100t |

Both have the same pins. The pin table is in Wiz's library, `lib/Hdl/Arty.wiz`
(`Arty.board`, from Digilent's master XDC); `lib/Hdl/Xdc.wiz` writes the XDC from it.
The designs use:

| signal | pin | port |
|---|---|---|
| 100 MHz clock | E3 | `clk` |
| UART RX (host → FPGA) | A9 | `uart_rx` |
| UART TX (FPGA → host) | D10 | `uart_tx` |
| LD4 … LD7 (green) | H5, J5, T9, T10 | `led[0]` … `led[3]` |

### The UART's clock rate

The serial port is 115200 baud 8N1, nominally. An FT2232 makes its baud rate from 3 MHz
with an integer divisor, so its "115200" is really 3 MHz / 26 = 115384.6 baud (0.16 %
fast). The board's divider is computed from that rate (`Ftdi.divisor` and
`clocksPerBit` in `src/Arty/Designs.wiz`): it is the host's bit period in clock cycles,
rounded down, 866 at 100 MHz (115473.4 baud, 0.08 % fast of the FT2232). The board has to
be a little fast of the host, never slow. `echo` buffers one byte, so it must send at
least as fast as it receives. With 868 (100 MHz / 115200, rounded) it dropped one byte in
every 2200 or so of a long burst on the board. The iCEstick never showed this: its
12 MHz / 104 = 115384.6 baud is exactly the FT2232's rate. The simulations model the
host at that rate too (`Host.num / Host.den` = 2600/3 cycles per bit).

## The designs

All are `Circuit Pins.code Board.code` values in `src/Arty/Designs.wiz`, built from the
UART of `src/Arty/Uart.wiz` (wiz-icestick-uart's, with ten-bit baud counters).

| design | what it does |
|---|---|
| `blinky` | a 27-bit counter, its top four bits on the LEDs (LD7 at 0.75 Hz) |
| `hello` | sends `Hello from Wiz!\r\n`, waits 0.34 s, again |
| `echo` | sends back every byte it receives |
| `squares` | for every byte `b`, stores the low byte of `b * b` at address `b` of a 1024-byte RAM and sends back what that address held before (0 the first time): a byte sent twice comes back as its square the second time. The RAM is a RAMB18E1, the multiply a DSP48E1. |

(The iCEstick's fourth design, the CRC service `proto`, is not ported: it would be the
same text again.)

## Building

You need Nix with flakes. `nix develop` gives a shell with `wiz`, `grail` (the Wiz flake,
pinned in `flake.lock`), yosys, Icarus Verilog and the openXC7 toolchain (pinned in
`flake.lock` too, `github:openXC7/toolchain-nix`): nextpnr (the himbaechel xilinx
architecture and its `nextpnr-xilinx` front end), Project X-Ray (`fasm2frames`,
`xc7frames2bit`) and prjxray-db. Nothing of openXC7 is in a binary cache: the first
`nix develop` builds nextpnr, Project X-Ray and the two chip databases from source.
`nix/chipdb.nix` builds only the two dies the Arty can carry (openXC7's own
`nextpnr-xilinx-chipdb.artix7` builds every Artix-7 die).

```sh
nix develop
grail build                 # check the designs, compile the driver
grail test                  # the simulation tests (tests/*.wiz)
.grail/bin/arty all         # gen, sim, bit, postsim for the A7-35T
.grail/bin/arty bit a100t   # bitstreams for the A7-100T
.grail/bin/arty bit both
```

The output is in `build/`: `NAME.v`, `arty.xdc`, `NAME.stat` (yosys's utilisation),
and per device `build/a35t/NAME.bit` (and `.fasm`, `.frames`, the nextpnr log, whose
"Max frequency" line `arty bit` prints).

Until the Wiz library modules `Hdl.Xdc` and `Hdl.Arty` are on Wiz's master, use a Wiz
checkout that has them (`grail` from its `.lake/build/bin`, which reads that checkout's
`lib/`).

## The PmodOLEDrgb on Pmod JA

A Digilent PmodOLEDrgb (SSD1331 controller, 96 × 64, 16-bit colour) on header JA, driven
by the controller, effects and ray tracers of
[wiz-icestick-uart](../wiz-icestick-uart) (branch `oled-demo`; `src/Arty/Oled*.wiz`,
`Fx*.wiz`, `Demo*.wiz`, `Sphere.wiz`, `Blobs.wiz` are its files with the module names
changed), and four Arty designs (`src/Arty/OledArty.wiz`, `src/Arty/Show.wiz`):

| design | what it shows |
|---|---|
| `oled_test` | a test pattern: white border, eight colour bars, a red-to-blue ramp, a grey ramp |
| `oled_demo` | the iCEstick's colour slideshow: plasma, stars, sine scroller, XOR |
| `oled_blobs` | the iCEstick's sphere tracer (two balls, smooth minimum) |
| `oled_show` | six effects, 8 s each: the four of `oled_demo`, the ray-traced ball over a floor, and the blobs with 30 steps a pixel (both balls every cycle), the normal and colour blended by the smooth minimum's weight (DSP slices), the floor and the shadows |

The OLED's eight signals are one port, `oled`, bits 0 … 7 on the Pmod's pins 1, 2, 3, 4,
7, 8, 9, 10 (CS, MOSI, unused, SCK, D/C, RES, VCCEN, PMODEN), and `OledArty.board h`
puts it on header `h` (`ja` … `jd`; `OledArty.defaultHeader` is `ja`).

**The clock.** The circuits are the iCEstick's, run one cycle in eight (12.5 MHz,
`Circuit.slow 3`): the SSD1331's serial clock may be at most 6.7 MHz and the serialiser
toggles it every cycle it runs, so a full frame (96 × 64 × 16 bits) takes 15.7 ms: 63.6
frames a second, back to back. The enable is a flip-flop (`ce`); every other register
holds unless it is high. The XDC of these designs constrains the clock at 80 ns (eight
periods: what the circuits' own paths have), and the one-period paths from `ce` are
checked with `scripts/sdfpath.py` on nextpnr's SDF (`arty bit` writes
`build/DEVICE/NAME.sdf`).

**Checks** (`arty gen oled_test oled_demo oled_blobs oled_show`): each circuit is run on
its own with short waits and frames back to back, and its pins go through the SSD1331
model of wiz-icestick-uart (`QModel`: the serial interface, the command table with its
argument counts, the window): the power-up in the PmodOLEDrgb's order and times, exactly
the program's command bytes, the controller's registers as wanted, and every frame,
12288 bytes into the whole panel, equal pixel by pixel to the effects evaluated directly
(the frames are written as `build/frames/NAME_K_tT.ppm`). Then the slowed-down circuit
runs 20000 cycles: the same command bytes, the reset pulse eight times as long, netlist =
values; and the board's design itself 20000 cycles for the Verilog simulations.

## Alternatives to openXC7

* **Vivado** (AMD/Xilinx, free WebPACK licence for these parts): `read_verilog
  build/NAME.v; read_xdc build/arty.xdc; synth_design -top NAME -part
  xc7a35ticsg324-1L; place_design; route_design; write_bitstream NAME.bit`. Note that
  the driver names one-bit ports bare (`uart_tx`), as nextpnr wants; Vivado sees the
  emitted `[0:0]` ports as `uart_tx[0]`.
* **F4PGA** (formerly SymbiFlow): yosys and VPR with the same Project X-Ray database;
  the Arty A7-35T is one of its reference boards. Installed through conda rather than Nix;
  not tried here.

## On the board

```sh
openFPGALoader -b arty_a7_35t build/a35t/NAME.bit     # SRAM (volatile); -f would write the flash
```

With a second FTDI device on the same bus (an iCEstick), `--ftdi-serial` failed
(libftdi -9); `--busdev-num BUS:DEV` (from `/sys/bus/usb/devices/*/busnum,devnum`)
works. The UART is `/dev/serial/by-id/usb-Digilent_Digilent_USB_Device_*-if01-port0`.

Results on an Arty A7-35T (2026-11-12, SRAM loads):

| design | check | result |
|---|---|---|
| `blinky` | LEDs, UART | LD4-LD7 count in binary; UART silent |
| `hello` | UART for 3 s | 8 × `Hello from Wiz!\r\n`, nothing else |
| `echo` | a string; 256 byte values; 4096 random bytes ×3; 32768 random bytes | all identical (with divider 866; see above) |
| `squares` | 10 bytes, then all 256 values twice | exactly as specified (RAMB18E1, DSP48E1) |
