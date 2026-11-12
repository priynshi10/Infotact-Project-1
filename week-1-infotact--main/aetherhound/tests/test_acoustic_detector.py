"""
Unit tests for Acoustic DSP features and Acoustic Anomaly Detector.
"""

import numpy as np
import pytest

from aetherhound.detection.acoustic_detector import AcousticDetector
from aetherhound.dsp.acoustic_processor import AcousticProcessor
from aetherhound.dsp.feature_extractor import (
    compute_periodicity_score,
    compute_rms_energy,
    compute_zero_crossing_rate,
    extract_acoustic_features,
)
from aetherhound.hardware.acoustic_capture import AudioChunk, inject_synthetic_audio_pulse
from aetherhound.hardware.config import AcousticConfig


def test_acoustic_features_rms_and_zcr():
    sr = 44100
    t = np.linspace(0, 1, sr)
    sine = 0.5 * np.sin(2 * np.pi * 1000 * t).astype(np.float32)

    rms = compute_rms_energy(sine)
    assert rms == pytest.approx(0.5 / np.sqrt(2), rel=0.05)

    zcr = compute_zero_crossing_rate(sine)
    # 1000 Hz in 44100 Hz has 2000 zero crossings per sec -> ~ 2000/44100 = 0.045
    assert zcr == pytest.approx(2000.0 / sr, rel=0.10)


def test_acoustic_processor_filtering():
    cfg = AcousticConfig(sample_rate_hz=44100, chunk_size=2048)
    proc = AcousticProcessor(cfg)

    # 10 Hz rumble (outside bandpass filter) + 1200 Hz tone
    t = np.arange(2048) / 44100.0
    signal_in = (0.4 * np.sin(2 * np.pi * 10 * t) + 0.3 * np.sin(2 * np.pi * 1200 * t)).astype(np.float32)

    chunk = AudioChunk(samples=signal_in, timestamp=10.0, sample_rate_hz=44100, channels=1, chunk_id=1)
    res = proc.process_chunk(chunk)

    # Filtered dominant frequency should match 1200 Hz, suppressing 10 Hz
    assert abs(res.features.dominant_frequency_hz - 1200.0) < 50.0


def test_acoustic_anomaly_detector_trigger():
    cfg = AcousticConfig(sample_rate_hz=44100, chunk_size=1024, energy_threshold_factor=2.0)
    proc = AcousticProcessor(cfg)
    detector = AcousticDetector(cfg, history_len=25, hysteresis_cooldown_sec=0.5)

    # Ambient low level
    rng = np.random.default_rng(99)
    ambient = rng.normal(0, 0.005, 1024).astype(np.float32)

    # 1. Warm up baseline
    for i in range(15):
        c = AudioChunk(samples=ambient.copy(), timestamp=i * 0.02, sample_rate_hz=44100, channels=1, chunk_id=i)
        pc = proc.process_chunk(c)
        detector.update(pc)

    # 2. Inject repeated bursts (on/off pattern)
    alerts = []
    for i in range(15, 30):
        if (i % 2) == 0:
            c = AudioChunk(samples=ambient.copy(), timestamp=i * 0.02, sample_rate_hz=44100, channels=1, chunk_id=i)
            c = inject_synthetic_audio_pulse(c, carrier_freq_hz=1500.0, amplitude=0.4)
        else:
            c = AudioChunk(samples=ambient.copy(), timestamp=i * 0.02, sample_rate_hz=44100, channels=1, chunk_id=i)

        pc = proc.process_chunk(c)
        alert = detector.update(pc)
        if alert:
            alerts.append(alert)

    assert len(alerts) >= 1
    assert alerts[0].status == "SUSPICIOUS ACOUSTIC ACTIVITY"
