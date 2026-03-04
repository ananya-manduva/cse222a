<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

This design implements a **PWM Breathing LED** — a hardware demo that makes all 8 output pins smoothly and continuously fade in and out, like a sleeping device's power indicator. The effect is achieved entirely in digital logic using a triangle-wave envelope counter driving a PWM comparator.

### Signal Chain

```
system clock
     │
     ▼
┌─────────────┐   envelope tick    ┌──────────────────┐
│  24-bit     │ ─────────────────► │  8-bit envelope  │
│  prescaler  │  (1 pulse per step)│  (triangle wave  │
└─────────────┘                    │   0 → 255 → 0)   │
                                   └────────┬─────────┘
                                            │ envelope value
                                            ▼
┌─────────────┐   pwm_cnt          ┌──────────────────┐
│  8-bit free │ ─────────────────► │   comparator     │ ──► uo_out[7:0]
│  PWM counter│                    │ (cnt < envelope) │     (all 8 bits)
└─────────────┘                    └──────────────────┘
```

1. A **24-bit prescaler** divides the system clock. The bit tapped depends on the speed setting, producing an envelope tick at different rates.
2. An **8-bit envelope counter** increments on each tick until it reaches 255, then decrements back to 0, repeating — forming a triangle wave.
3. A free-running **8-bit PWM counter** compares against the envelope: output is HIGH when `pwm_cnt < envelope`, LOW otherwise. This makes the duty cycle proportional to the envelope value.
4. All 8 `uo_out` pins carry the same PWM signal — connect any LED (with a resistor) to any output pin to see the effect.

### Pin Mapping

| Signal       | Bits    | Description                                              |
|--------------|---------|----------------------------------------------------------|
| `ui_in[1:0]` | speed   | `00` slow (~1 breath/2s @ 12 MHz) · `11` fast          |
| `ui_in[2]`   | dir_lock| `0` = triangle (breathe) · `1` = sawtooth (fade-in loop)|
| `ui_in[7:3]` | —       | Unused                                                   |
| `uo_out[7:0]`| output  | PWM signal — all 8 pins identical                       |
| `uio_*`      | —       | Unused (bidir pins configured as inputs, driven low)    |

### Speed Settings

| `ui_in[1:0]` | Clock bit tapped | Steps/sec @ 12 MHz | Breath period |
|---|---|---|---|
| `00` | bit 19 | ~11 | ~46 s |
| `01` | bit 17 | ~46 | ~11 s |
| `10` | bit 15 | ~183 | ~2.8 s |
| `11` | bit 13 | ~732 | ~0.7 s |

## How to test

### On the bench

1. Connect an LED (with a 330 Ω resistor) between any `uo_out` pin and GND.
2. Power the chip and assert `rst_n` high.
3. Set `ui_in[1:0]` to `10` for a comfortable breathing speed.
4. The LED should smoothly fade in and out repeatedly.
5. Try `ui_in[2] = 1` for a sawtooth (instant-on, slow-fade) pattern.
6. Adjust `ui_in[1:0]` to change the breathing speed.

### Simulation

Run the self-checking testbench with [Icarus Verilog](https://steveicarus.github.io/iverilog/):

```bash
cd test
make sim
```

Inspect waveforms:
```bash
make wave   # opens GTKWave
```

### Testbench Coverage

The testbench (`test/tb.v`) verifies the following properties:

| Test | What is checked |
|---|---|
| 1. Reset state | `uo_out`, `envelope`, and `pwm_cnt` all zero after reset |
| 2. Prescaler | Increments by 1 each clock cycle |
| 3. Envelope advance | Envelope increases over time at the fastest speed setting |
| 4. Envelope bounds | Envelope stays within [0, 255]; `env_dir` is a valid 1-bit signal |
| 5. PWM duty cycle | Fraction of HIGH cycles over 256 clocks matches envelope value (±2) |
| 6. Output consistency | All 8 `uo_out` bits are always identical (never partially high) |
| 7. Sawtooth mode | With `dir_lock=1`, envelope never decreases (100 k cycles) |
| 8. Bidir pins | `uio_oe` and `uio_out` are always 0 |
| 9. Re-reset | Re-asserting reset clears envelope back to 0 |

The testbench is self-checking: each test prints `PASS` or `FAIL` independently and a final summary counts totals. A VCD dump is generated for waveform inspection.

## External hardware

- 1–8 LEDs with 330 Ω current-limiting resistors to GND (one per `uo_out` pin).
- No other external components required.

## GenAI Usage

GenAI (Claude by Anthropic) was used to assist with:
- Structuring the Verilog module to match TinyTapeout's `tt_um_*` interface template.
- Writing the self-checking testbench scaffold and individual test cases.

All generated code was reviewed and validated by simulation before submission.