// A zero-initialised shift register with a clock enable feeds a multiplier and a pin.
// synth_xilinx copies it into the DSP48E1 A/B input registers (AREG=BREG=1) and leaves
// the fabric flip-flops that still drive `q` with INIT x instead of INIT 0.
module top(input clk, input en, input d, output [7:0] q, output [15:0] p);
  reg [7:0] sh = 8'h00;
  reg [15:0] pr = 16'd0;
  wire [15:0] x = {8'd0, sh};
  always @(posedge clk) begin
    if (en) sh <= {d, sh[7:1]};
    pr <= x * x;
  end
  assign q = sh; assign p = pr;
endmodule
