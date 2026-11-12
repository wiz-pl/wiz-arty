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
