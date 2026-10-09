module \$_DFF_P_ (input D, C, output Q);
  sky130_fd_sc_hd__dfxtp_1 _TECHMAP_REPLACE_ (.CLK(C), .D(D), .Q(Q));
endmodule
module \$_DFFE_PP_ (input D, C, E, output Q);
  sky130_fd_sc_hd__edfxtp_1 _TECHMAP_REPLACE_ (.CLK(C), .D(D), .DE(E), .Q(Q));
endmodule
module \$_DFF_PN0_ (input D, C, R, output Q);
  sky130_fd_sc_hd__dfrtp_1 _TECHMAP_REPLACE_ (.CLK(C), .D(D), .RESET_B(R), .Q(Q));
endmodule
