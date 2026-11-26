"""
Unit tests for AirHopper GPU Display Cable FM Transmitter and Scanner.
"""

import numpy as np
import pytest
from aetherhound.malware.airhopper import AirHopperMockMalware
from aetherhound.dsp.fm_scanner import AirHopperDetector


def test_airhopper_fm_generation():
    malware = AirHopperMockMalware(carrier_freq_hz=98.5e6, sample_rate=240000)
    iq = malware.generate_fm_baseband("1010", freq_dev_hz=25000.0, bit_rate_bps=500.0)
    assert len(iq) == int(240000 / 500.0 * 4)
    assert np.iscomplexobj(iq)
    assert np.allclose(np.abs(iq), 1.0, atol=1e-3)


def test_airhopper_detection():
    detector = AirHopperDetector(sample_rate=240000, threshold_kurtosis=1.8)
    # 1. Clean noise should not trigger
    noise = (np.random.randn(2048) + 1j * np.random.randn(2048)).astype(np.complex64)
    res_noise = detector.detect_fm_covert_channel(noise)
    assert not res_noise["is_detected"]

    # 2. Modulated AirHopper transmission
    malware = AirHopperMockMalware(sample_rate=240000)
    iq_signal = malware.generate_fm_baseband("10101010", freq_dev_hz=40000.0, bit_rate_bps=1000.0)
    res_signal = detector.detect_fm_covert_channel(iq_signal)
    assert res_signal["freq_dev_hz"] > 15000.0
