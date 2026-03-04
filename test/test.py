# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge


@cocotb.test()
async def test_reset_state(dut):
    """After reset, all outputs should be 0."""
    dut._log.info("Test 1: Reset state")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)

    assert dut.uo_out.value == 0,  f"uo_out should be 0 in reset, got {dut.uo_out.value}"
    assert dut.uio_out.value == 0, f"uio_out should be 0, got {dut.uio_out.value}"
    assert dut.uio_oe.value == 0,  f"uio_oe should be 0, got {dut.uio_oe.value}"

    dut._log.info("PASS: Reset state correct")


@cocotb.test()
async def test_bidir_pins(dut):
    """uio_oe and uio_out must always be 0 (bidir pins unused)."""
    dut._log.info("Test 2: Bidir pins are inputs and driven low")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut.ena.value = 1
    dut.ui_in.value = 0b00000011   # speed=11 (fastest)
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 100)

    assert dut.uio_oe.value  == 0, f"uio_oe should be 0, got {dut.uio_oe.value}"
    assert dut.uio_out.value == 0, f"uio_out should be 0, got {dut.uio_out.value}"

    dut._log.info("PASS: Bidir pins correct")


@cocotb.test()
async def test_output_bits_uniform(dut):
    """All 8 uo_out bits must always be identical (all-0 or all-1)."""
    dut._log.info("Test 3: All uo_out bits are identical")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut.ena.value = 1
    dut.ui_in.value = 0b00000011   # speed=11 (fastest)
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst_n.value = 1

    for cycle in range(2000):
        await RisingEdge(dut.clk)
        val = dut.uo_out.value.integer
        assert val == 0x00 or val == 0xFF, \
            f"Cycle {cycle}: uo_out={val:#04x} — bits are not uniform!"

    dut._log.info("PASS: All output bits always uniform over 2000 cycles")


@cocotb.test()
async def test_pwm_duty_cycle(dut):
    """
    PWM duty cycle should track the envelope value.
    At speed=11 (fastest), one envelope step = 2^13 * 2 = 16384 clocks.
    We run long enough for envelope to reach a stable mid-range value,
    then measure high-fraction over exactly 256 clocks (one PWM period).
    Expected: high_count ≈ envelope value (±4 tolerance).
    """
    dut._log.info("Test 4: PWM duty cycle tracks envelope")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut.ena.value = 1
    dut.ui_in.value = 0b00000011   # speed=11 (fastest), triangle mode
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst_n.value = 1

    # Run until envelope has advanced enough (envelope steps happen every ~16k clocks)
    # 40 steps * 16384 clocks/step = ~655k clocks to reach envelope ~40
    await ClockCycles(dut.clk, 700_000)

    # Measure duty cycle over 256 consecutive clocks (one full PWM period)
    high_count = 0
    for _ in range(256):
        await RisingEdge(dut.clk)
        if dut.uo_out.value.integer == 0xFF:
            high_count += 1

    # Read envelope via internal signal
    envelope = dut.envelope.value.integer
    dut._log.info(f"  envelope={envelope}  high_count={high_count}")

    assert abs(high_count - envelope) <= 4, \
        f"Duty cycle mismatch: high_count={high_count}, envelope={envelope}"

    dut._log.info(f"PASS: duty cycle={high_count}/256 matches envelope={envelope}")


@cocotb.test()
async def test_envelope_increases_from_zero(dut):
    """
    After reset, envelope starts at 0 and must increase over time.
    At speed=11, one step takes ~16k clocks. Run 50k clocks and confirm
    envelope has moved above 0.
    """
    dut._log.info("Test 5: Envelope increases from 0 after reset")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut.ena.value = 1
    dut.ui_in.value = 0b00000011
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst_n.value = 1

    await ClockCycles(dut.clk, 50_000)

    envelope = dut.envelope.value.integer
    assert envelope > 0, f"Envelope still 0 after 50k clocks — not advancing!"

    dut._log.info(f"PASS: envelope={envelope} after 50k clocks")


@cocotb.test()
async def test_sawtooth_mode(dut):
    """
    With ui_in[2]=1 (dir_lock), envelope must only increase or wrap 255→0.
    It must never decrease mid-ramp.
    """
    dut._log.info("Test 6: Sawtooth mode — envelope never decreases")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut.ena.value = 1
    dut.ui_in.value = 0b00000111   # speed=11, dir_lock=1
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst_n.value = 1

    prev_env = 0
    for cycle in range(200_000):
        await RisingEdge(dut.clk)
        curr_env = dut.envelope.value.integer
        # A decrease is only valid as the natural 255→0 wrap
        if curr_env < prev_env:
            assert prev_env == 255 and curr_env == 0, \
                f"Cycle {cycle}: envelope decreased {prev_env}→{curr_env} without wrapping!"
        prev_env = curr_env

    dut._log.info("PASS: Envelope never decreased outside of 255→0 wrap")


@cocotb.test()
async def test_re_reset_clears_envelope(dut):
    """Re-asserting reset at any time must clear envelope back to 0."""
    dut._log.info("Test 7: Re-reset clears envelope")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut.ena.value = 1
    dut.ui_in.value = 0b00000011
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst_n.value = 1

    # Let it run so envelope advances
    await ClockCycles(dut.clk, 50_000)
    env_before = dut.envelope.value.integer
    dut._log.info(f"  envelope before re-reset: {env_before}")

    # Re-assert reset
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)

    assert dut.envelope.value.integer == 0, \
        f"Envelope not cleared on re-reset: {dut.envelope.value.integer}"
    assert dut.uo_out.value == 0, \
        f"uo_out not 0 during reset: {dut.uo_out.value}"

    dut.rst_n.value = 1
    dut._log.info("PASS: Re-reset correctly clears envelope and output")


@cocotb.test()
async def test_speed_select(dut):
    """
    Slower speed setting should produce fewer envelope steps in the same
    number of clocks. Compare step count at speed=11 vs speed=01.
    """
    dut._log.info("Test 8: Speed select affects breathing rate")

    RUN_CLOCKS = 100_000

    # --- Measure steps at speed=11 (fastest) ---
    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut.ena.value = 1
    dut.ui_in.value = 0b00000011
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst_n.value = 1

    await ClockCycles(dut.clk, RUN_CLOCKS)
    env_fast = dut.envelope.value.integer

    # --- Measure steps at speed=00 (slowest) ---
    dut.rst_n.value = 0
    dut.ui_in.value = 0b00000000
    await ClockCycles(dut.clk, 4)
    dut.rst_n.value = 1

    await ClockCycles(dut.clk, RUN_CLOCKS)
    env_slow = dut.envelope.value.integer

    dut._log.info(f"  envelope after {RUN_CLOCKS} clocks: fast={env_fast}, slow={env_slow}")

    assert env_fast > env_slow, \
        f"Speed=11 should advance envelope faster than speed=00, but fast={env_fast} slow={env_slow}"

    dut._log.info("PASS: Faster speed setting advances envelope more quickly")
    