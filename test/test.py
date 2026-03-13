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
    dut.ui_in.value = 0b00000011
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
    dut.ui_in.value = 0b00000011
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst_n.value = 1

    for cycle in range(2000):
        await RisingEdge(dut.clk)
        val = dut.uo_out.value.to_unsigned()
        assert val == 0x00 or val == 0xFF, \
            f"Cycle {cycle}: uo_out={val:#04x} — bits are not uniform!"

    dut._log.info("PASS: All output bits always uniform over 2000 cycles")


@cocotb.test()
async def test_pwm_activity(dut):
    """
    After reset, uo_out must both go HIGH and LOW within a reasonable window,
    confirming the PWM is actively running. Uses only external pins.
    """
    dut._log.info("Test 4: PWM is active (output toggles)")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut.ena.value = 1
    dut.ui_in.value = 0b00000011
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst_n.value = 1

    saw_high = False
    saw_low  = False
    for _ in range(200_000):
        await RisingEdge(dut.clk)
        v = dut.uo_out.value.to_unsigned()
        if v == 0xFF: saw_high = True
        if v == 0x00: saw_low  = True
        if saw_high and saw_low:
            break

    assert saw_high, "uo_out never went HIGH — envelope not advancing!"
    assert saw_low,  "uo_out never went LOW — PWM counter not running!"
    dut._log.info("PASS: PWM is actively toggling output")


@cocotb.test()
async def test_duty_cycle_increases(dut):
    """
    Duty cycle (fraction of HIGH cycles) must increase over time from reset,
    confirming the envelope is counting upward. Uses only external pins.
    """
    dut._log.info("Test 5: Duty cycle increases as envelope rises")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut.ena.value = 1
    dut.ui_in.value = 0b00000011
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst_n.value = 1

    # Window 1: early (envelope still low)
    await ClockCycles(dut.clk, 20_000)
    high_1 = 0
    for _ in range(256):
        await RisingEdge(dut.clk)
        if dut.uo_out.value.to_unsigned() == 0xFF:
            high_1 += 1

    # Window 2: later (envelope has risen)
    await ClockCycles(dut.clk, 200_000)
    high_2 = 0
    for _ in range(256):
        await RisingEdge(dut.clk)
        if dut.uo_out.value.to_unsigned() == 0xFF:
            high_2 += 1

    dut._log.info(f"  early duty={high_1}/256, later duty={high_2}/256")

    assert high_2 > high_1, \
        f"Duty cycle did not increase over time: early={high_1} later={high_2}"

    dut._log.info("PASS: Duty cycle increased as envelope rose")


@cocotb.test()
async def test_sawtooth_duty_rises(dut):
    """
    In sawtooth mode (dir_lock=1), duty cycle must increase between two
    consecutive sample windows. Uses only external pins.
    """
    dut._log.info("Test 6: Sawtooth mode — duty cycle only increases")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut.ena.value = 1
    dut.ui_in.value = 0b00000111   # speed=11, dir_lock=1
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst_n.value = 1

    await ClockCycles(dut.clk, 20_000)
    high_1 = 0
    for _ in range(256):
        await RisingEdge(dut.clk)
        if dut.uo_out.value.to_unsigned() == 0xFF:
            high_1 += 1

    await ClockCycles(dut.clk, 100_000)
    high_2 = 0
    for _ in range(256):
        await RisingEdge(dut.clk)
        if dut.uo_out.value.to_unsigned() == 0xFF:
            high_2 += 1

    dut._log.info(f"  sawtooth window1={high_1}/256, window2={high_2}/256")

    assert high_2 >= high_1 or high_2 == 0, \
        f"Sawtooth duty cycle decreased without wrap: {high_1} -> {high_2}"

    dut._log.info("PASS: Sawtooth duty cycle did not decrease")


@cocotb.test()
async def test_re_reset_clears_output(dut):
    """Re-asserting reset must bring uo_out back to 0. Uses only external pins."""
    dut._log.info("Test 7: Re-reset clears output")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut.ena.value = 1
    dut.ui_in.value = 0b00000011
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 50_000)

    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)

    assert dut.uo_out.value == 0, \
        f"uo_out not 0 during reset: {dut.uo_out.value}"
    assert dut.uio_out.value == 0, \
        f"uio_out not 0 during reset: {dut.uio_out.value}"

    dut.rst_n.value = 1
    dut._log.info("PASS: Re-reset clears output to 0")


@cocotb.test()
async def test_speed_select(dut):
    """
    speed=11 must produce higher duty cycle than speed=00 after the same
    number of clocks (faster envelope advance). Uses only external pins.
    """
    dut._log.info("Test 8: Speed select affects breathing rate")

    RUN_CLOCKS = 200_000

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    # Measure at speed=11
    dut.ena.value = 1
    dut.ui_in.value = 0b00000011
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 4)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, RUN_CLOCKS)

    high_fast = 0
    for _ in range(256):
        await RisingEdge(dut.clk)
        if dut.uo_out.value.to_unsigned() == 0xFF:
            high_fast += 1

    # Measure at speed=00
    dut.rst_n.value = 0
    dut.ui_in.value = 0b00000000
    await ClockCycles(dut.clk, 4)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, RUN_CLOCKS)

    high_slow = 0
    for _ in range(256):
        await RisingEdge(dut.clk)
        if dut.uo_out.value.to_unsigned() == 0xFF:
            high_slow += 1

    dut._log.info(f"  fast={high_fast}/256, slow={high_slow}/256")

    assert high_fast > high_slow, \
        f"speed=11 should have higher duty cycle than speed=00: fast={high_fast} slow={high_slow}"

    dut._log.info("PASS: Faster speed setting produces higher duty cycle sooner")
    