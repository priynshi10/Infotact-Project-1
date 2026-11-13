"""
DSP Feature Extractor & Classical Signal Detector.
Calculates SNR, peak frequencies, spectral kurtosis, entropy, and harmonic ratios
to isolate artificial covert channel signatures from normal server mechanics.
"""

import numpy as np
from typing import Dict, Any, Tuple, List

class SignalFeatureDetector:
    """
    Classical SIGINT feature extraction engine.
    Analyzes frequency distributions, detects carrier spikes, and measures SNR.
    """

    def __init__(self, sample_rate: int):
        self.sample_rate = sample_rate

    def detect_prominent_peaks(self, freq_bins: np.ndarray, psd_db: np.ndarray, top_k: int = 5) -> List[Tuple[float, float, float]]:
        """
        Identify top spectral peaks with estimated SNR against local noise floor.
        Returns: List of (peak_freq_hz, peak_power_db, local_snr_db)
        """
        # Exclude extreme low DC frequencies (< 50 Hz)
        valid_mask = freq_bins >= 50.0
        v_freqs = freq_bins[valid_mask]
        v_psd = psd_db[valid_mask]

        if len(v_psd) < 10:
            return []

        # Local median filter as estimated background noise floor
        noise_floor = np.median(v_psd)
        peaks = []

        # Find local maxima
        for i in range(1, len(v_psd) - 1):
            if v_psd[i] > v_psd[i - 1] and v_psd[i] > v_psd[i + 1]:
                snr = v_psd[i] - noise_floor
                peaks.append((float(v_freqs[i]), float(v_psd[i]), float(snr)))

        # Sort by peak power descending
        peaks.sort(key=lambda x: x[1], reverse=True)
        return peaks[:top_k]

    def compute_spectral_entropy(self, psd_linear: np.ndarray) -> float:
        """
        Calculate Shannon Spectral Entropy.
        Flat white noise -> Entropy ~ 1.0.
        Single artificial covert sine carrier -> Entropy drops significantly towards 0.0.
        """
        p = psd_linear / (np.sum(psd_linear) + 1e-12)
        p = p[p > 0]
        entropy = -np.sum(p * np.log2(p + 1e-12))
        max_entropy = np.log2(len(psd_linear) + 1e-12)
        return float(entropy / (max_entropy + 1e-12))

    def compute_spectral_kurtosis(self, signal_chunk: np.ndarray) -> float:
        """
        Compute Spectral Kurtosis of time domain chunk.
        Highlights transient non-Gaussian bursts (e.g. pulsed covert transmissions).
        """
        mean = np.mean(signal_chunk)
        std = np.std(signal_chunk) + 1e-12
        z = (signal_chunk - mean) / std
        kurt = np.mean(z**4) - 3.0  # Excess kurtosis
        return float(kurt)

    def extract_channel_metrics(self, signal_chunk: np.ndarray, freq_bins: np.ndarray, psd_db: np.ndarray) -> Dict[str, Any]:
        """Comprehensive signal diagnostic report."""
        peaks = self.detect_prominent_peaks(freq_bins, psd_db, top_k=3)
        psd_linear = 10.0 ** (psd_db / 10.0)
        entropy = self.compute_spectral_entropy(psd_linear)
        kurtosis = self.compute_spectral_kurtosis(signal_chunk)

        primary_freq = peaks[0][0] if peaks else 0.0
        primary_power = peaks[0][1] if peaks else -120.0
        primary_snr = peaks[0][2] if peaks else 0.0

        return {
            "primary_peak_hz": primary_freq,
            "peak_power_db": primary_power,
            "peak_snr_db": primary_snr,
            "spectral_entropy": entropy,
            "kurtosis": kurtosis,
            "top_peaks": peaks
        }
