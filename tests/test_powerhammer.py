"""
Unit tests for PowerHammer Conducted Emission Simulator and Powerline Filter.
"""

import numpy as np
import pytest
from aetherhound.malware.powerhammer import PowerHammerMockMalware
from aetherhound.dsp.powerline_filter import PowerlineSidebandFilter


def test_powerhammer_synthesis():
    malware = PowerHammerMockMalware(mains_freq_hz=50.0, sample_rate_hz=10000)
    samples = malware.synthesize_powerline_signal("1010", burst_rate_bps=25.0)
    assert len(samples) == 1600
    assert np.max(samples) > 8.0


def test_powerline_sideband_detection():
    detector = PowerlineSidebandFilter(sample_rate_hz=10000, cutoff_hz=150.0)
    malware = PowerHammerMockMalware(mains_freq_hz=50.0, sample_rate_hz=10000)

    # 1. Clean mains should NOT trigger
    t = np.linspace(0, 0.5, 5000, endpoint=False)
    clean_mains = (10.0 * np.sin(2.0 * np.pi * 50.0 * t)).astype(np.float32)
    res_clean = detector.detect_conducted_bursts(clean_mains, threshold_rms=0.2)
    assert not res_clean["is_detected"]

    # 2. Modulated PowerHammer stream should trigger
    burst_signal = malware.synthesize_powerline_signal("1111", burst_rate_bps=20.0, modulation_depth_amps=1.2)
    res_burst = detector.detect_conducted_bursts(burst_signal, threshold_rms=0.2)
    assert res_burst["is_detected"]
    assert res_burst["sideband_rms_amps"] > 0.4
