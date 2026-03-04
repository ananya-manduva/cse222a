/*
 * tt_um_pwm_breath.v
 *
 * PWM Breathing LED for TinyTapeout (Skywater 130nm)
 *
 * Generates a smooth "breathing" fade-in / fade-out on all 8 output pins
 * using an 8-bit PWM signal whose duty cycle is swept up and down by a
 * triangle-wave envelope counter.
 *
 * ── Pin Mapping ────────────────────────────────────────────────────────────
 *  ui_in[1:0]  speed select
 *                00 = slowest  (divide clock by 2^20, ~1 Hz breath @ 12 MHz)
 *                01 = slow     (divide clock by 2^18)
 *                10 = fast     (divide clock by 2^16)
 *                11 = fastest  (divide clock by 2^14)
 *  ui_in[2]    direction lock: 0 = breathing (triangle), 1 = fade-in only
 *  ui_in[7:3]  unused
 *
 *  uio_in      unused (all tied to input, output driven 0)
 *
 *  uo_out[7:0] PWM output – connect LEDs (with current-limiting resistors)
 *                           to any or all of these pins. All pins carry the
 *                           same PWM signal.
 *
 * ── Theory of Operation ────────────────────────────────────────────────────
 *  1. A 24-bit prescaler divides the system clock down to an "envelope tick".
 *  2. On each envelope tick, an 8-bit envelope counter increments or
 *     decrements, bouncing between 0 and 255 (triangle wave).
 *  3. A free-running 8-bit PWM counter compares against the envelope value:
 *       pwm_out = (pwm_counter < envelope) ? 1 : 0
 *     This produces a duty cycle proportional to the envelope – making the
 *     LED appear to smoothly brighten and dim.
 *  4. All 8 uo_out bits are driven with the same PWM bit so any LED wired to
 *     any output pin shows the effect.
 */

`default_nettype none

module tt_um_pwm_breath (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);

    // Tie unused IOs
    assign uio_out = 8'b0;
    assign uio_oe  = 8'b0;

    // ── User controls ────────────────────────────────────────────────────
    wire [1:0] speed     = ui_in[1:0];
    wire       dir_lock  = ui_in[2];   // 1 = fade-in only (sawtooth)

    // ── Prescaler ────────────────────────────────────────────────────────
    // 24-bit counter; we tap different bits based on speed select.
    reg [23:0] prescaler;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) prescaler <= 24'd0;
        else        prescaler <= prescaler + 1'b1;
    end

    // Envelope tick: one pulse per envelope step
    // speed 00 → bit 19 toggle  (~1 breath / 2 sec @ 12 MHz)
    // speed 01 → bit 17
    // speed 10 → bit 15
    // speed 11 → bit 13
    reg env_tick;
    always @(*) begin
        case (speed)
            2'b00: env_tick = prescaler[19];
            2'b01: env_tick = prescaler[17];
            2'b10: env_tick = prescaler[15];
            2'b11: env_tick = prescaler[13];
        endcase
    end

    // Edge-detect on env_tick to get a single-cycle pulse
    reg env_tick_prev;
    wire env_pulse = env_tick & ~env_tick_prev;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) env_tick_prev <= 1'b0;
        else        env_tick_prev <= env_tick;
    end

    // ── Envelope (triangle wave) ─────────────────────────────────────────
    reg [7:0] envelope;
    reg       env_dir;   // 0 = counting up, 1 = counting down

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            envelope <= 8'd0;
            env_dir  <= 1'b0;
        end else if (env_pulse) begin
            if (dir_lock) begin
                // Sawtooth: just count up and wrap
                envelope <= envelope + 1'b1;
            end else begin
                // Triangle: bounce between 0 and 255
                if (env_dir == 1'b0) begin
                    if (envelope == 8'd255) begin
                        env_dir  <= 1'b1;
                        envelope <= envelope - 1'b1;
                    end else begin
                        envelope <= envelope + 1'b1;
                    end
                end else begin
                    if (envelope == 8'd0) begin
                        env_dir  <= 1'b0;
                        envelope <= envelope + 1'b1;
                    end else begin
                        envelope <= envelope - 1'b1;
                    end
                end
            end
        end
    end

    // ── PWM counter (free-running 8-bit) ────────────────────────────────
    reg [7:0] pwm_cnt;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) pwm_cnt <= 8'd0;
        else        pwm_cnt <= pwm_cnt + 1'b1;
    end

    // ── PWM output ───────────────────────────────────────────────────────
    wire pwm_out = (pwm_cnt < envelope) ? 1'b1 : 1'b0;

    // Drive all 8 output pins with the same PWM signal
    assign uo_out = {8{pwm_out}};

endmodule