# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers    import RisingEdge, FallingEdge, Timer, with_timeout, ClockCycles
from cocotb.types import Logic
from cocotb.types import LogicArray
from cocotb.result      import TestFailure, SimTimeoutError
from cocotb.utils import get_sim_time

async def await_half_sclk(dut):
    """Wait for the SCLK signal to go high or low."""
    start_time = cocotb.utils.get_sim_time(units="ns")
    while True:
        await ClockCycles(dut.clk, 1)
        # Wait for half of the SCLK period (10 us)
        if (start_time + 100*100*0.5) < cocotb.utils.get_sim_time(units="ns"):
            break
    return

def ui_in_logicarray(ncs, bit, sclk):
    """Setup the ui_in value as a LogicArray."""
    return LogicArray(f"00000{ncs}{bit}{sclk}")

async def send_spi_transaction(dut, r_w, address, data):
    """
    Send an SPI transaction with format:
    - 1 bit for Read/Write
    - 7 bits for address
    - 8 bits for data
    
    Parameters:
    - r_w: boolean, True for write, False for read
    - address: int, 7-bit address (0-127)
    - data: LogicArray or int, 8-bit data
    """
    # Convert data to int if it's a LogicArray
    if isinstance(data, LogicArray):
        data_int = int(data)
    else:
        data_int = data
    # Validate inputs
    if address < 0 or address > 127:
        raise ValueError("Address must be 7-bit (0-127)")
    if data_int < 0 or data_int > 255:
        raise ValueError("Data must be 8-bit (0-255)")
    # Combine RW and address into first byte
    first_byte = (int(r_w) << 7) | address
    # Start transaction - pull CS low
    sclk = 0
    ncs = 0
    bit = 0
    # Set initial state with CS low
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 1)
    # Send first byte (RW + Address)
    for i in range(8):
        bit = (first_byte >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # Send second byte (Data)
    for i in range(8):
        bit = (data_int >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # End transaction - return CS high
    sclk = 0
    ncs = 1
    bit = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 600)
    return ui_in_logicarray(ncs, bit, sclk)

@cocotb.test()
async def test_spi(dut):
    dut._log.info("Start SPI test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("Test project behavior")
    dut._log.info("Write transaction, address 0x00, data 0xF0")
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xF0)  # Write transaction
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 1000)

    dut._log.info("Write transaction, address 0x01, data 0xCC")
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xCC)  # Write transaction
    assert dut.uio_out.value == 0xCC, f"Expected 0xCC, got {dut.uio_out.value}"
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x30 (invalid), data 0xAA")
    ui_in_val = await send_spi_transaction(dut, 1, 0x30, 0xAA)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Read transaction (invalid), address 0x00, data 0xBE")
    ui_in_val = await send_spi_transaction(dut, 0, 0x30, 0xBE)
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 100)
    
    dut._log.info("Read transaction (invalid), address 0x41 (invalid), data 0xEF")
    ui_in_val = await send_spi_transaction(dut, 0, 0x41, 0xEF)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x02, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x04, data 0xCF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xCF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x00")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x01")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x01)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("SPI test completed successfully")



@cocotb.test()
async def test_pwm_freq(dut):
    """Verify PWM = 3 kHz ±1% on uo_out[0]."""
    cocotb.start_soon(Clock(dut.clk, 100, units="ns").start())
    dut.ena.value    = 1
    dut.ui_in.value  = ui_in_logicarray(1,0,0)
    dut.rst_n.value  = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value  = 1
    await ClockCycles(dut.clk, 5)

    # 1) Enable static output on bit 0
    await send_spi_transaction(dut, 1, 0x00, 0x01)
    # 2) Load 50% duty BEFORE PWM enable
    await send_spi_transaction(dut, 1, 0x04, 0x80)
    # 3) Enable PWM on bit 0
    await send_spi_transaction(dut, 1, 0x02, 0x01)
    await ClockCycles(dut.clk, 100)

    # —— first rising edge with with_timeout ——
    prev = int(dut.uo_out.value) & 1
    t1   = None
    while True:
        try:
            await with_timeout(RisingEdge(dut.clk), 1_000_000, units="ns")
        except SimTimeoutError:
            raise TestFailure("Timed out waiting for first rising uo_out[0]")
        curr = int(dut.uo_out.value) & 1
        if prev == 0 and curr == 1:
            t1 = get_sim_time(units="ns")
            break
        prev = curr

    # —— second rising edge with with_timeout ——
    prev = curr
    t2   = None
    while True:
        try:
            await with_timeout(RisingEdge(dut.clk), 1_000_000, units="ns")
        except SimTimeoutError:
            raise TestFailure("Timed out waiting for second rising uo_out[0]")
        curr = int(dut.uo_out.value) & 1
        if prev == 0 and curr == 1:
            t2 = get_sim_time(units="ns")
            break
        prev = curr

    period_ns = t2 - t1
    freq_khz  = 1e6 / period_ns
    dut._log.info(f"Measured PWM freq = {freq_khz:.3f} kHz")
    if not (2.97 <= freq_khz <= 3.03):
        raise TestFailure(f"Freq out of tolerance: {freq_khz:.3f} kHz")
    dut._log.info("PWM Frequency OK")


@cocotb.test()
async def test_pwm_duty(dut):
    """Verify PWM duty = 0%, 50%, 100% ±1% on uo_out[0]."""
    cocotb.start_soon(Clock(dut.clk, 100, units="ns").start())
    dut.ena.value    = 1
    dut.ui_in.value  = ui_in_logicarray(1,0,0)
    dut.rst_n.value  = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value  = 1
    await ClockCycles(dut.clk, 5)

    # Enable static output and PWM once
    await send_spi_transaction(dut, 1, 0x00, 0x01)
    await send_spi_transaction(dut, 1, 0x02, 0x01)
    await ClockCycles(dut.clk, 50)

    tests = [(0x00,  0.0), (0x80,  50.0), (0xFF, 100.0)]
    tol   = 1.0

    for val, exp in tests:
        dut._log.info(f"Setting duty = 0x{val:02X} ({exp:.1f}%")

        # reload fresh duty
        await send_spi_transaction(dut, 1, 0x02, 0x00)
        await send_spi_transaction(dut, 1, 0x04, val)
        await send_spi_transaction(dut, 1, 0x02, 0x01)
        await ClockCycles(dut.clk, 100)

        prev = int(dut.uo_out.value) & 1

        if exp == 0.0:
            # 0% should stay low
            seen = False
            while True:
                try:
                    await with_timeout(RisingEdge(dut.clk), 1_000_000, units="ns")
                except SimTimeoutError:
                    break
                curr = int(dut.uo_out.value) & 1
                if prev == 0 and curr == 1:
                    seen = True
                    break
                prev = curr
            if seen:
                raise TestFailure("Duty=0% unexpectedly went high")
            dut._log.info("0% stayed low")

        elif exp == 100.0:
            # 100% should stay high
            seen = False
            while True:
                try:
                    await with_timeout(RisingEdge(dut.clk), 1_000_000, units="ns")
                except SimTimeoutError:
                    break
                curr = int(dut.uo_out.value) & 1
                if prev == 1 and curr == 0:
                    seen = True
                    break
                prev = curr
            if seen:
                raise TestFailure("Duty=100% unexpectedly went low")
            dut._log.info("100% stayed high")

        else:
            # measure mid-range duty
            # rising edge
            prev = int(dut.uo_out.value) & 1
            t_r  = None
            while True:
                try:
                    await with_timeout(RisingEdge(dut.clk), 1_000_000, units="ns")
                except SimTimeoutError:
                    raise TestFailure("Timeout waiting for rising edge")
                curr = int(dut.uo_out.value) & 1
                if prev == 0 and curr == 1:
                    t_r = get_sim_time(units="ns")
                    break
                prev = curr

            # falling edge
            prev = curr
            t_f  = None
            while True:
                try:
                    await with_timeout(RisingEdge(dut.clk), 1_000_000, units="ns")
                except SimTimeoutError:
                    raise TestFailure("Timeout waiting for falling edge")
                curr = int(dut.uo_out.value) & 1
                if prev == 1 and curr == 0:
                    t_f = get_sim_time(units="ns")
                    break
                prev = curr

            # next rising edge for full period
            prev = curr
            t2   = None
            while True:
                try:
                    await with_timeout(RisingEdge(dut.clk), 1_000_000, units="ns")
                except SimTimeoutError:
                    raise TestFailure("Timeout waiting for second rising edge")
                curr = int(dut.uo_out.value) & 1
                if prev == 0 and curr == 1:
                    t2 = get_sim_time(units="ns")
                    break
                prev = curr

            high_ns   = t_f - t_r
            period_ns = t2  - t_r
            measured  = high_ns/period_ns*100.0
            dut._log.info(f"Measured duty = {measured:.1f}%")
            if abs(measured - exp) > tol:
                raise TestFailure(f"Duty {measured:.1f}% ≠ {exp:.1f}% ±{tol}%")

    dut._log.info("PWM Duty test OK")

"""
@cocotb.test()
async def test_pwm_freq(dut):
    """"""Verify PWM = 3 kHz ±1% on uo_out[0].""""""
    cocotb.start_soon(Clock(dut.clk, 100, units="ns").start())
    dut.ena.value    = 1
    dut.ui_in.value  = ui_in_logicarray(1,0,0)
    dut.rst_n.value  = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value  = 1
    await ClockCycles(dut.clk, 5)

    # 1) Enable static output on bit 0
    await send_spi_transaction(dut, 1, 0x00, 0x01)
    # 2) Load 50% duty BEFORE PWM enable
    await send_spi_transaction(dut, 1, 0x04, 0x80)
    # 3) Enable PWM on bit 0
    await send_spi_transaction(dut, 1, 0x02, 0x01)

    await ClockCycles(dut.clk, 100)

    # inline poll for first rising edge on uo_out[0]
    deadline = get_sim_time(units="ns") + 1_000_000
    prev     = int(dut.uo_out.value) & 1
    t1       = None


    while get_sim_time(units="ns") < deadline:
        await RisingEdge(dut.clk)
        curr = int(dut.uo_out.value) & 1
        if prev == 0 and curr == 1:
            t1 = get_sim_time(units="ns")
            break
        prev = curr
    if t1 is None:
        raise TestFailure("Timed out waiting for first rising uo_out[0]")

    # inline poll for second rising edge on uo_out[0]
    deadline = get_sim_time(units="ns") + 1_000_000
    prev     = curr
    t2       = None

    
    while get_sim_time(units="ns") < deadline:
        await RisingEdge(dut.clk)
        curr = int(dut.uo_out.value) & 1
        if prev == 0 and curr == 1:
            t2 = get_sim_time(units="ns")
            break
        prev = curr
    if t2 is None:
        raise TestFailure("Timed out waiting for second rising uo_out[0]")

    period_ns = t2 - t1
    freq_khz  = 1e6 / period_ns
    dut._log.info(f"Measured PWM freq = {freq_khz:.3f} kHz")
    # ±1% tolerance in kHz: 3.00 ±0.03 => [2.97, 3.03]
    if not (2.97 <= freq_khz <= 3.03):                     
        raise TestFailure(f"Freq out of tolerance: {freq_khz:.3f} kHz")
    dut._log.info("PWM Frequency OK")

@cocotb.test()
async def test_pwm_duty(dut):
    """"""Verify PWM duty = 0%, 50%, 100% ±1% on uo_out[0].""""""
    cocotb.start_soon(Clock(dut.clk, 100, units="ns").start())
    dut.ena.value    = 1
    dut.ui_in.value  = ui_in_logicarray(1,0,0)
    dut.rst_n.value  = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value  = 1
    await ClockCycles(dut.clk, 5)

    # Enable static output and PWM once
    await send_spi_transaction(dut, 1, 0x00, 0x01)
    await send_spi_transaction(dut, 1, 0x02, 0x01)
    await ClockCycles(dut.clk, 50)

    tests = [(0x00,  0.0), (0x80,  50.0), (0xFF, 100.0)]
    tol   = 1.0
    #
    for val, exp in tests:
        dut._log.info(f"Setting duty = 0x{val:02X} ({exp:.1f}%)")

        # reload fresh duty
        await send_spi_transaction(dut, 1, 0x02, 0x00)
        await send_spi_transaction(dut, 1, 0x04, val)
        await send_spi_transaction(dut, 1, 0x02, 0x01)

        await ClockCycles(dut.clk, 100)

        if exp == 0.0:
            # 0% should stay low
            deadline = get_sim_time(units="ns") + 1_000_000
            prev     = int(dut.uo_out.value) & 1
            seen     = False
            while get_sim_time(units="ns") < deadline:
                await RisingEdge(dut.clk)
                curr = int(dut.uo_out.value) & 1
                if prev == 0 and curr == 1:
                    seen = True
                    break
                prev = curr
            if seen:
                raise TestFailure("Duty=0% unexpectedly went high")
            dut._log.info("0% stayed low")


        elif exp == 100.0:
            # 100% should stay high
            deadline = get_sim_time(units="ns") + 1_000_000
            prev     = int(dut.uo_out.value) & 1
            seen     = False
            while get_sim_time(units="ns") < deadline:
                await RisingEdge(dut.clk)
                curr = int(dut.uo_out.value) & 1
                if prev == 1 and curr == 0:
                    seen = True
                    break
                prev = curr
            if seen:
                raise TestFailure("Duty=100% unexpectedly went low")
            dut._log.info("100% stayed high")


        else:
            # measure mid-range duty
            # rising
            deadline = get_sim_time(units="ns") + 1_000_000
            prev     = int(dut.uo_out.value) & 1
            t_r      = None
            while get_sim_time(units="ns") < deadline:
                await RisingEdge(dut.clk)
                curr = int(dut.uo_out.value) & 1
                if prev == 0 and curr == 1:
                    t_r = get_sim_time(units="ns")
                    break
                prev = curr
            if t_r is None:
                raise TestFailure("Timeout waiting for rising edge")
            # falling
            deadline = get_sim_time(units="ns") + 1_000_000
            prev     = curr
            t_f      = None


            while get_sim_time(units="ns") < deadline:
                await RisingEdge(dut.clk)
                curr = int(dut.uo_out.value) & 1
                if prev == 1 and curr == 0:
                    t_f = get_sim_time(units="ns")
                    break
                prev = curr
            if t_f is None:
                raise TestFailure("Timeout waiting for falling edge")
            # next rising
            deadline = get_sim_time(units="ns") + 1_000_000
            prev     = curr
            t2       = None


            while get_sim_time(units="ns") < deadline:
                await RisingEdge(dut.clk)
                curr = int(dut.uo_out.value) & 1
                if prev == 0 and curr == 1:
                    t2 = get_sim_time(units="ns")
                    break
                prev = curr
            if t2 is None:
                raise TestFailure("Timeout waiting for second rising edge")
            high_ns   = t_f - t_r
            period_ns = t2  - t_r
            measured  = high_ns/period_ns*100.0
            dut._log.info(f"Measured duty = {measured:.1f}%")
            if abs(measured - exp) > tol:
                raise TestFailure(f"Duty {measured:.1f}% ≠ {exp:.1f}% ±{tol}%")

    dut._log.info("PWM Duty test OK")
    """
