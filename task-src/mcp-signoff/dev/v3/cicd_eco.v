// cicd: 3 stage CIC decimator with gain scaler, level and peak meters.
// one clock. apb style register port (no wait states, no protocol checker).
//
// regs (word addr):
//   0 CTRL   [0] en  [1] dump  [2] apply (w1: commit shadows at next decimation)
//            [3] agc  [5:4] ratio code
//   1 GAIN   [9:0] gain shadow, unsigned 2.8 ([9:8] coarse, [7:0] fine)
//   2 SHIFT  [3:0] output shift shadow
//   3 STAT   r: [0] ovr [1] busy [2] pend [3] tmode   w1 [0]: clear ovr
//   4 LEVEL  r: level[23:8], clears level
//   5 PEAK   r: peak[17:2]
//   6 KEY    w: C1D5 then 2A3E unlocks production test mode
//   7 TEST   w (test mode only): [8] go. reruns the multiply on the operands
//            already held, starting the sequencer at phase 1. ignored if busy
//
// test mode also turns ratio code 3 into R = 2 for fast vector application.
//
// ratio R = 4 << ratio code (4, 8, 16, 32). shadows go live together at the
// first decimation strobe after apply. sync restarts the decimation phase;
// with dump set, a sync also pushes out the partial sample if two or more
// inputs are pending. if inputs stall with a partial sample pending, the
// watchdog pushes it out after 255 idle clocks.
// agc: every clipped output steps the fine gain down by one lsb.
// an idle channel (comb output exactly zero) skips the multiply: the
// sequencer goes straight to its last phase and the output is forced to zero.
module cicd (
  input  wire               clk,
  input  wire               rst_n,
  input  wire               psel,
  input  wire               penable,
  input  wire               pwrite,
  input  wire [3:0]         paddr,
  input  wire [15:0]        pwdata,
  output reg  [15:0]        prdata,
  input  wire               in_valid,
  input  wire signed [11:0] in_data,
  input  wire               sync,
  output reg                out_valid,
  output reg  signed [15:0] out_data,
  output reg  [7:0]         out_tag,
  output wire               ovr
);
  localparam W = 27;

  // ---------------------------------------------------------------- regs
  wire wr = psel & penable & pwrite;
  wire rd = psel & penable & ~pwrite;

  reg        en, dump, agc, pend, ovr_r, armed, tmode;
  reg  [1:0] r_sh, r_act;
  reg  [9:0] gain_sh;
  reg  [1:0] gcoarse;
  reg  [7:0] gfine;
  reg  [3:0] shift_sh, shift_act;

  wire ce_dec;
  wire drop;
  wire clip;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      en <= 1'b0; dump <= 1'b0; agc <= 1'b0; pend <= 1'b0; ovr_r <= 1'b0;
      armed <= 1'b0; tmode <= 1'b0;
      r_sh <= 2'd0; gain_sh <= 10'h000; shift_sh <= 4'd0;
      r_act <= 2'd0; gcoarse <= 2'd0; gfine <= 8'd0; shift_act <= 4'd0;
    end else begin
      if (wr && paddr == 4'd0) begin
        en <= pwdata[0]; dump <= pwdata[1]; agc <= pwdata[3]; r_sh <= pwdata[5:4];
        if (pwdata[2]) pend <= 1'b1;
      end
      if (wr && paddr == 4'd1) gain_sh <= pwdata[9:0];
      if (wr && paddr == 4'd2) shift_sh <= pwdata[3:0];
      if (wr && paddr == 4'd6) begin
        armed <= (pwdata == 16'hc1d5);
        if (armed && pwdata == 16'h2a3e) tmode <= 1'b1;
      end
      if (ce_dec && pend) begin
        r_act <= r_sh; gcoarse <= gain_sh[9:8]; gfine <= gain_sh[7:0];
        shift_act <= shift_sh;
        pend <= 1'b0;
      end else if (agc && clip && gfine != 8'd0) begin
        gfine <= gfine - 8'd1;
      end
      if (drop) ovr_r <= 1'b1;
      else if (wr && paddr == 4'd3 && pwdata[0]) ovr_r <= 1'b0;
    end
  end
  assign ovr = ovr_r;

  // ---------------------------------------------------------- decimation
  wire       vld = in_valid & en;
  reg  [4:0] cnt;
  reg  [7:0] wd;
  wire [4:0] r_last = (tmode && r_act == 2'd3) ? 5'd1 : (5'd4 << r_act) - 5'd1;
  wire       dump_now = sync & dump & (cnt > 5'd1);
  wire       flush = en & ~in_valid & (wd == 8'hff);
  assign ce_dec = (vld & ((cnt == r_last) | dump_now)) | flush;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n)      cnt <= 5'd0;
    else if (sync || flush) cnt <= 5'd0;
    else if (vld)    cnt <= (cnt == r_last) ? 5'd0 : cnt + 5'd1;
  end

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n)                          wd <= 8'd0;
    else if (!en || ce_dec || cnt == 0)  wd <= 8'd0;
    else                                 wd <= wd + 8'd1;
  end

  // integrators, full rate
  reg signed [W-1:0] i1, i2, i3;
  always @(posedge clk)
    if (vld) begin
      i1 <= i1 + {{(W-12){in_data[11]}}, in_data};
      i2 <= i2 + i1;
      i3 <= i3 + i2;
    end

  // decimated sample. the comb chain runs at the decimated rate as one
  // unregistered cascade, two clocks after the sample is taken.
  reg signed [W-1:0] s0, z1, z2, z3, c3;
  reg ce_d1, ce_d2, ce_d3;
  always @(posedge clk) if (ce_dec) s0 <= i3;
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin ce_d1 <= 1'b0; ce_d2 <= 1'b0; ce_d3 <= 1'b0; end
    else begin ce_d1 <= ce_dec; ce_d2 <= ce_d1; ce_d3 <= ce_d2; end
  end
  wire signed [W-1:0] d1 = s0 - z1;
  wire signed [W-1:0] d2 = d1 - z2;
  wire signed [W-1:0] d3 = d2 - z3;
  always @(posedge clk)
    if (ce_d2) begin z1 <= s0; z2 <= d1; z3 <= d2; c3 <= d3; end

  // sample index
  reg [7:0] idx;
  always @(posedge clk) if (ce_dec) idx <= idx + 8'd1;

  // ------------------------------------------------------------- scaler
  reg        busy;
  reg  [1:0] ph;
  wire last    = busy & (ph == 2'd3);
  wire start   = ce_d3 & (~busy | last);
  wire preload = wr & (paddr == 4'd7) & tmode & pwdata[8] & ~busy & ~ce_d3;   // eco2
  assign drop  = ce_d3 & busy & ~last;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n)        begin busy <= 1'b0; ph <= 2'd0; end
    else if (!en)      begin busy <= 1'b0; ph <= 2'd0; end
    else if (preload)  begin busy <= 1'b1; ph <= 2'd1; end
    else if (start)    begin busy <= 1'b1; ph <= zskip ? 2'd3 : 2'd0; end
    else if (busy)     begin ph <= ph + 2'd1; if (last) busy <= 1'b0; end
  end

  // free running copy of the live gain, retimes the commit/agc muxes away
  // from the operand register
  reg [9:0] gain_q;
  always @(posedge clk) gain_q <= {gcoarse, gfine};

  wire signed [W-1:0] c3n = c3 >>> (3 * r_act);
  wire               zskip = 1'b0;   // eco1: zero skip removed
  reg                zop;
  reg  signed [17:0]  opx, opx_q;
  reg         [9:0]   opg;
  reg         [7:0]   tag_op;
  reg  signed [28:0]  prod;

  always @(posedge clk)
    if (start) begin opx <= c3n[23:6]; opg <= gain_q; tag_op <= idx; zop <= zskip; end

  // free running copy for the peak meter, keeps the compare off the
  // multiplier operand net
  always @(posedge clk) opx_q <= opx;

  always @(posedge clk)
    if (busy && ph == 2'd2) prod <= opx * $signed({1'b0, opg});

  wire signed [28:0] scaled = prod >>> shift_act;
  assign clip = last & ~zop & ((scaled > 29'sd32767) | (scaled < -29'sd32768));
  wire signed [15:0] ysat = (scaled >  29'sd32767) ? 16'sh7fff :
                            (scaled < -29'sd32768) ? 16'sh8000 : scaled[15:0];

  always @(posedge clk)
    if (last) begin out_data <= zop ? 16'sd0 : ysat; out_tag <= tag_op; end
  always @(posedge clk or negedge rst_n)
    if (!rst_n) out_valid <= 1'b0; else out_valid <= last;

  // ------------------------------------------------------------- meters
  wire [17:0] opx_mag = opx_q[17] ? -opx_q : opx_q;
  reg  [17:0] pk;
  always @(posedge clk)
    if (busy && ph == 2'd3) begin
      if (tag_op == 8'd0)    pk <= opx_mag;
      else if (opx_mag > pk) pk <= opx_mag;
    end

  wire [15:0] ymag = out_data[15] ? -out_data : out_data;
  reg  [23:0] level;
  wire lvl_rd = rd && paddr == 4'd4;
  always @(posedge clk)
    if (lvl_rd || out_valid)
      level <= lvl_rd ? 24'd0 : level + {8'd0, ymag};

  // ------------------------------------------------------------ readback
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) prdata <= 16'd0;
    else if (psel && !penable && !pwrite)
      case (paddr)
        4'd0:    prdata <= {10'd0, r_sh, agc, pend, dump, en};
        4'd1:    prdata <= {6'd0, gain_sh};
        4'd2:    prdata <= {12'd0, shift_sh};
        4'd3:    prdata <= {12'd0, tmode, pend, busy, ovr_r};
        4'd4:    prdata <= level[23:8];
        4'd5:    prdata <= pk[17:2];
        default: prdata <= 16'd0;
      endcase
  end
endmodule
