`default_nettype none

module spi_peripheral (
    input  wire        clk,             // 10 MHz system clock
    input  wire        rst_n,           // active-low reset
    input  wire        nCS,             // active-low chip select
    input  wire        SCLK,            // SPI serial clock
    input  wire        COPI,            // master-out, peripheral-in data

    output reg  [7:0]  en_reg_out_7_0,   // enables for uo_out[7:0]
    output reg  [7:0]  en_reg_out_15_8,  // enables for uio_out[7:0]
    output reg  [7:0]  en_reg_pwm_7_0,   // PWM enables for uo_out[7:0]
    output reg  [7:0]  en_reg_pwm_15_8,  // PWM enables for uio_out[7:0]
    output reg  [7:0]  pwm_duty_cycle    // duty (0x00=0%, 0xFF=100%)
);

  //Clock Domain Crossing
    reg [1:0] cs_meta, cs_sync;
    reg [1:0] sclk_meta, sclk_sync;
    reg [1:0] copi_meta, copi_sync;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cs_meta   <= 2'b11;
            sclk_meta <= 2'b00;
            copi_meta <= 2'b00;
            cs_sync   <= 2'b11;
            sclk_sync <= 2'b00;
            copi_sync <= 2'b00;
        end else begin
            // stage 1: sample raw inputs
            cs_meta[0]   <= nCS;
            cs_meta[1]   <= cs_meta[0];
            sclk_meta[0] <= SCLK;
            sclk_meta[1] <= sclk_meta[0];
            copi_meta[0] <= COPI;
            copi_meta[1] <= copi_meta[0];
            // stage 2: synchronize into clk domain
            cs_sync[0]   <= cs_meta[1];
            cs_sync[1]   <= cs_sync[0];
            sclk_sync[0] <= sclk_meta[1];
            sclk_sync[1] <= sclk_sync[0];
            copi_sync[0] <= copi_meta[1];
            copi_sync[1] <= copi_sync[0];
        end
    end

wire cs_i   = cs_sync[1];
wire sclk_i = sclk_sync[1];
wire copi_i = copi_sync[1];

//Edge detection logic
  reg prev_cs, prev_sclk;
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      prev_cs   <= 1'b1;
      prev_sclk <= 1'b0;
    end else begin
      prev_cs   <= cs_i;
      prev_sclk <= sclk_i;
    end
  end

  wire cs_falling  =  prev_cs & ~cs_i;
  wire sclk_rising = ~prev_sclk &  sclk_i;

  reg [4:0]  bit_count;
  reg [15:0] shift_reg;
  reg [15:0] rx_word;
  reg        rx_word_valid;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      bit_count     <= 5'd0;
      shift_reg     <= 16'd0;
      rx_word       <= 16'd0;
      rx_word_valid <= 1'b0;
    end else begin
      rx_word_valid <= 1'b0;
      if (cs_falling) begin
        bit_count <= 5'd0;
        shift_reg <= 16'd0;
      end else if (!cs_i && sclk_rising) begin
        shift_reg <= { shift_reg[14:0], copi_i };
        if (bit_count == 5'd15) begin
          rx_word       <= { shift_reg[14:0], copi_i };
          rx_word_valid <= 1'b1;
          bit_count     <= 5'd0;
        end else begin
          bit_count <= bit_count + 1;
        end
      end
    end
  end

//Communication with the PWM module
    
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      en_reg_out_7_0   <= 8'd0;
      en_reg_out_15_8  <= 8'd0;
      en_reg_pwm_7_0   <= 8'd0;
      en_reg_pwm_15_8  <= 8'd0;
      pwm_duty_cycle   <= 8'd0;
    end else if (rx_word_valid && rx_word[15]) begin
      case (rx_word[14:8])
        7'd0: en_reg_out_7_0  <= rx_word[7:0];
        7'd1: en_reg_out_15_8 <= rx_word[7:0];
        7'd2: en_reg_pwm_7_0  <= rx_word[7:0];
        7'd3: en_reg_pwm_15_8 <= rx_word[7:0];
        7'd4: pwm_duty_cycle  <= rx_word[7:0];
        default: ; 
      endcase
    end
  end

endmodule

`default_nettype wire
