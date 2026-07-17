module sigmoid( ck, x, y );
   input ck;
   input signed [15:0] x;
   output signed [15:0] y;

   parameter NUM_BITS = 16;
   parameter NUM_BITS_INT_PART = 4;
   parameter NUM_BITS_FRAC_PART = 12;

   parameter XINF = -22282;
   parameter XMIN = -13312;
   parameter XMED = 0;
   parameter XMAX = 13312;
   parameter XSUP = 22282;

   parameter ZERO = 0;
   parameter ONE = 4096;

   parameter P2K1 = 58;
   parameter P2K0 = 314;
   parameter P3K2 = 165;
   parameter P3K1 = 1116;
   parameter P3K0 = 2057;
   parameter P4K2 = -165;
   parameter P4K1 = 1116;
   parameter P4K0 = 2039;
   parameter P5K1 = 58;
   parameter P5K0 = 3782;

   reg signed [31:0]  tmp, tmp_2, tmp_4;
   reg signed [15:0]  tmp_3, y_tmp;
   assign y = y_tmp;
   always @ ( posedge ck )
     begin
	if( x <= XINF )
	  y_tmp = ZERO;
	else
	  if( x <= XMIN )
	    begin
	       tmp = P2K1 * x + P2K0 * ONE;
	       y_tmp = tmp[27:12];
	    end
	  else
	    if( x <= XMED )
	      begin
		 tmp_2 = P3K2 * x + P3K1 * ONE;
		 tmp_3 = tmp_2[27:12];
		 tmp_4 = x * tmp_3 + P3K0 * ONE;
		 y_tmp = tmp_4[27:12];
	      end
	    else
	      if( x <= XMAX )
		begin
		   tmp_2 = P4K2 * x + P4K1 * ONE;
		   tmp_3 = tmp_2[27:12];
		   tmp_4 = x * tmp_3 + P4K0 * ONE;
		   y_tmp = tmp_4[27:12];
		end
	      else
		if( x <= XSUP )
		  begin
		     tmp = P5K1 * x + P5K0 * ONE;
		     y_tmp = tmp[27:12];
		  end
		else
		  y_tmp = ONE;
     end
endmodule
