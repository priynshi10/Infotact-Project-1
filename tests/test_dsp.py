"""
Unit Tests for AetherHound Digital Signal Processing (DSP) Suite.
"""

import numpy as np
import pytest
from aetherhound.dsp.filters import SignalFilter
from aetherhound.dsp.spectral import SpectralAnalyzer
from aetherhound.dsp.detector_dsp import SignalFeatureDetector
from aetherhound.dsp.accelerated_dsp import AcceleratedDSPEngine

def test_signal_filters():
    sr = 48000
    filt = SignalFilter(sample_rate=sr)
    t = np.linspace(0, 1.0, sr, endpoint=False)
    # 50 Hz power hum + 2000 Hz signal
    sig = np.sin(2 * np.pi * 50 * t) + np.sin(2 * np.pi * 2000 * t)

    # Notch 50 Hz
    notched = filt.notch_filter(sig, [50.0])
    fft_orig = np.abs(np.fft.rfft(sig))
    fft_notched = np.abs(np.fft.rfft(notched))
    idx_50 = int(50.0 / (sr / len(sig)))
    assert fft_notched[idx_50] < fft_orig[idx_50] * 0.1

    # Bandpass 1500 - 2500 Hz
    bp = filt.bandpass_filter(sig, 1500.0, 2500.0)
    assert len(bp) == len(sig)

def test_spectral_analyzer():
    sr = 48000
    sa = SpectralAnalyzer(sample_rate=sr)
    chunk = np.random.randn(2048).astype(np.float32)
    freq_bins, psd_db = sa.compute_psd(chunk)
    assert len(freq_bins) == len(psd_db)
    assert len(freq_bins) == sa.n_fft // 2 + 1

    # Check waterfall roll
    wf1 = sa.get_waterfall()
    assert wf1.shape == (sa.history_depth, sa.n_bins)
    # Compute patch
    patch = sa.compute_spectrogram_patch(chunk, target_shape=(40, 64))
    assert patch.shape == (40, 64)
    assert 0.0 <= patch.min() and patch.max() <= 1.0

def test_feature_detector():
    sr = 48000
    det = SignalFeatureDetector(sample_rate=sr)
    t = np.linspace(0, 0.1, int(sr * 0.1), endpoint=False)
    # Sine tone at 1800 Hz
    tone = np.sin(2 * np.pi * 1800.0 * t).astype(np.float32)

    freq_bins = np.fft.rfftfreq(len(tone), d=1.0/sr)
    psd_db = 10.0 * np.log10(np.abs(np.fft.rfft(tone))**2 + 1e-12)

    metrics = det.extract_channel_metrics(tone, freq_bins, psd_db)
    assert "primary_peak_hz" in metrics
    assert abs(metrics["primary_peak_hz"] - 1800.0) < 50.0
    assert metrics["peak_snr_db"] > 10.0

def test_accelerated_dsp_engine():
    engine = AcceleratedDSPEngine(buffer_size=2048)
    sig = np.random.randn(2048).astype(np.float32)
    mag = engine.fast_magnitude_spectrum(sig)
    assert len(mag) == 1025
    bench = engine.benchmark_latency(iterations=100)
    assert bench["avg_latency_microseconds"] < 1000.0  # Sub-millisecond
    assert bench["max_theoretical_fps"] > 30.0
