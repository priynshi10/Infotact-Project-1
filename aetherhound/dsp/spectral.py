"""
DSP Spectral Analysis & Waterfall Engine.
Computes real-time FFTs, STFT spectrogram matrices, Welch PSD, and maintains
rolling waterfall buffers for live terminal visualization and ML inference.
"""

import numpy as np
from typing import Tuple, Optional
from aetherhound.config import DSPOptimizationConfig

class SpectralAnalyzer:
    """
    High-Speed Spectral Engine.
    Converts streaming time-domain physical signals into calibrated frequency
    spectrograms and waterfalls.
    """

    def __init__(self, sample_rate: int, config: Optional[DSPOptimizationConfig] = None):
        self.sample_rate = sample_rate
        self.config = config or DSPOptimizationConfig()
        self.n_fft = self.config.n_fft
        self.hop_length = self.config.hop_length

        # Hann window pre-computed for maximum performance
        self.window = np.hanning(self.n_fft).astype(np.float32)

        # Pre-calculate frequency bins
        self.freq_bins = np.fft.rfftfreq(self.n_fft, d=1.0 / self.sample_rate)

        # Rolling Waterfall Matrix: Shape (history_depth, n_bins)
        self.history_depth = self.config.waterfall_history_depth
        self.n_bins = len(self.freq_bins)
        self.waterfall_buffer = np.zeros((self.history_depth, self.n_bins), dtype=np.float32)

    def compute_psd(self, signal_chunk: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute single-slice power spectral density using Hann windowed FFT.
        Returns: (freq_bins, psd_db)
        """
        if len(signal_chunk) < self.n_fft:
            padded = np.pad(signal_chunk, (0, self.n_fft - len(signal_chunk)))
        else:
            padded = signal_chunk[:self.n_fft]

        windowed = padded * self.window
        spectrum = np.fft.rfft(windowed)
        power = (np.abs(spectrum) ** 2) / (self.n_fft * self.sample_rate)
        # Convert to dB
        psd_db = 10.0 * np.log10(power + 1e-12)

        # Push to rolling waterfall
        self.waterfall_buffer = np.roll(self.waterfall_buffer, -1, axis=0)
        self.waterfall_buffer[-1, :] = psd_db

        return self.freq_bins, psd_db

    def compute_rf_psd(self, complex_iq_chunk: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute PSD for complex I/Q samples from SDR.
        Returns: (freq_bins, psd_db) centered at 0 Hz IF.
        """
        size = min(len(complex_iq_chunk), self.n_fft)
        window = np.hanning(size)
        windowed = complex_iq_chunk[:size] * window
        spectrum = np.fft.fftshift(np.fft.fft(windowed))
        power = np.abs(spectrum) ** 2 / size
        psd_db = 10.0 * np.log10(power + 1e-12)
        freq_bins = np.fft.fftshift(np.fft.fftfreq(size, d=1.0 / self.sample_rate))
        return freq_bins, psd_db

    def compute_spectrogram_patch(self, signal_chunk: np.ndarray, target_shape: Tuple[int, int] = (40, 64)) -> np.ndarray:
        """
        Extract a normalized 2D spectrogram patch of fixed shape (time_slices, freq_bins)
        suitable for direct feedforward into the PyTorch Autoencoder.
        """
        n_slices, n_freqs = target_shape
        # Ensure we have enough samples for STFT
        required_samples = (n_slices - 1) * self.hop_length + self.n_fft
        if len(signal_chunk) < required_samples:
            repeats = int(np.ceil(required_samples / len(signal_chunk)))
            extended = np.tile(signal_chunk, repeats)[:required_samples]
        else:
            extended = signal_chunk[:required_samples]

        slices = []
        for i in range(n_slices):
            start = i * self.hop_length
            segment = extended[start:start + self.n_fft] * self.window
            spec = np.abs(np.fft.rfft(segment))
            spec_db = 20.0 * np.log10(spec + 1e-6)
            slices.append(spec_db)

        raw_spectrogram = np.array(slices, dtype=np.float32)  # (n_slices, full_bins)

        # Max-pool across frequency bins to preserve all narrowband covert carriers
        full_bins = raw_spectrogram.shape[1]
        factor = max(1, full_bins // n_freqs)
        trunc_bins = n_freqs * factor
        pooled = np.max(raw_spectrogram[:, :trunc_bins].reshape(n_slices, n_freqs, factor), axis=-1)

        # Calibrated global dB normalization ([-65.0 dB, +15.0 dB] -> [0.0, 1.0])
        norm_spec = np.clip((pooled - (-65.0)) / (15.0 - (-65.0)), 0.0, 1.0).astype(np.float32)
        return norm_spec

    def get_waterfall(self) -> np.ndarray:
        """Return the current rolling waterfall matrix."""
        return self.waterfall_buffer.copy()
