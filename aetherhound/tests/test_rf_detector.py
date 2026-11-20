"""
Unit tests for RF DSP pipeline and Statistical Anomaly Detector.
"""

import numpy as np
import pytest

from aetherhound.detection.rf_detector import RFDetector
from aetherhound.dsp.fft_engine import compute_complex_fft, compute_power_spectrum_db
from aetherhound.dsp.rf_processor import RFProcessor
from aetherhound.hardware.config import RFConfig
from aetherhound.hardware.rf_capture import IQSampleWindow, inject_synthetic_rf_carrier


def test_fft_and_power_spectrum():
    sr = 2_048_000.0
    fc = 433_920_000.0
    n = 1024
    t = np.arange(n) / sr

    # Generate pure tone at +100 kHz offset
    tone_freq = 100_000.0
    iq = np.exp(1j * 2 * np.pi * tone_freq * t).astype(np.complex64)

    freqs, power_db = compute_power_spectrum_db(iq, fft_size=n, sample_rate_hz=sr, center_freq_hz=fc)

    assert len(freqs) == n
    assert len(power_db) == n

    # Peak should occur at approximately fc + tone_freq
    peak_idx = int(np.argmax(power_db))
    peak_freq = freqs[peak_idx]
    expected_freq = fc + tone_freq
    assert abs(peak_freq - expected_freq) < (sr / n)


def test_rf_processor_noise_floor_and_peaks():
    cfg = RFConfig(fft_size=1024, sample_rate_hz=2_048_000, center_freq_hz=433_920_000)
    processor = RFProcessor(cfg)

    # Ambient thermal noise + strong carrier
    rng = np.random.default_rng(42)
    noise = (rng.normal(0, 0.05, 2048) + 1j * rng.normal(0, 0.05, 2048)).astype(np.complex64)

    window = IQSampleWindow(
        samples=noise,
        timestamp=100.0,
        center_freq_hz=cfg.center_freq_hz,
        sample_rate_hz=cfg.sample_rate_hz,
        window_id=1,
    )

    # Without carrier, should not find excessive peak above noise
    proc1 = processor.process_window(window)
    assert proc1.noise_floor_db < -15.0

    # Inject carrier
    mod_window = inject_synthetic_rf_carrier(window, carrier_offset_hz=200_000.0, amplitude=0.8)
    proc2 = processor.process_window(mod_window)

    assert len(proc2.peaks) >= 1
    assert proc2.max_deviation_db > 15.0


def test_rf_detector_persistence_and_alert():
    cfg = RFConfig(fft_size=1024, detection_threshold_sigma=3.5)
    processor = RFProcessor(cfg)
    detector = RFDetector(cfg, min_persistence_windows=3)

    rng = np.random.default_rng(123)
    base_noise = (rng.normal(0, 0.05, 2048) + 1j * rng.normal(0, 0.05, 2048)).astype(np.complex64)

    # 1. Warm up baseline with clean noise
    for i in range(10):
        win = IQSampleWindow(base_noise.copy(), timestamp=100.0 + i * 0.1, center_freq_hz=433.92e6, sample_rate_hz=2.048e6, window_id=i)
        p_win = processor.process_window(win)
        alert = detector.update(p_win)
        assert alert is None

    # 2. Inject carrier persistently
    alerts = []
    for i in range(5):
        win = IQSampleWindow(base_noise.copy(), timestamp=101.0 + i * 0.1, center_freq_hz=433.92e6, sample_rate_hz=2.048e6, window_id=10 + i)
        mod_win = inject_synthetic_rf_carrier(win, carrier_offset_hz=100_000.0, amplitude=0.9)
        p_win = processor.process_window(mod_win)
        alert = detector.update(p_win)
        if alert:
            alerts.append(alert)

    # Should trigger alert after min_persistence_windows (3)
    assert len(alerts) >= 1
    assert alerts[0].status == "SUSPICIOUS RF ACTIVITY"
    assert abs(alerts[0].detected_freq_hz - (433.92e6 + 100_000.0)) < 10_000.0
