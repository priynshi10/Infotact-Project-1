"""
Unit tests for Optical Sensor Driver and Manchester Pulse Demodulator.
"""

import numpy as np
import pytest
from aetherhound.sensors.optical_receiver import OpticalReceiver
from aetherhound.dsp.optical_demod import ManchesterOpticalDemodulator


def test_optical_sensor_ambient_capture():
    sensor = OpticalReceiver(sample_rate_hz=50000, ambient_lux=300.0)
    frame = sensor.capture_frame(duration_sec=0.1)
    assert len(frame) == 5000
    assert np.mean(frame) > 280.0


def test_manchester_optical_demodulation():
    sample_rate = 50000
    bit_rate = 1000.0
    spb = int(sample_rate / bit_rate)
    demod = ManchesterOpticalDemodulator(sample_rate_hz=sample_rate, bit_rate_bps=bit_rate)

    bit_stream = "1010"
    pulses = []
    for b in bit_stream:
        if b == "1":
            pulses.extend([20.0] * (spb // 2) + [-20.0] * (spb // 2))
        else:
            pulses.extend([-20.0] * (spb // 2) + [20.0] * (spb // 2))

    signal_array = np.array(pulses, dtype=np.float32)
    res = demod.demodulate(signal_array)
    assert res["is_detected"]
    assert res["recovered_bits"] == "1010"
