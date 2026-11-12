// Two LEDs: one follows a switch, one is a registered copy of it.
module top(input clk, input [0:0] sw, output [1:0] led);
  reg r = 1'b0;
  always @(posedge clk) r <= sw;
  assign led = {r, sw};
endmodule
