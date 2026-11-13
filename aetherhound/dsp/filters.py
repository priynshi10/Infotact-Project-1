"""
Digital Signal Processing - Filters and Spectral Cleaning Module.
Implements bandpass, notch, and background suppression filters to isolate
weak acoustic and RF covert channel emissions from background server room noise.
"""

import numpy as np
from scipy import signal
from typing import List, Tuple, Optional

class SignalFilter:
    """
    Modular Digital Filter Suite for Acoustic and RF streams.
    Cleans raw physical signals before spectrogram conversion and ML ingestion.
    """

    def __init__(self, sample_rate: int):
        self.sample_rate = sample_rate
        self._sos_cache = {}

    def bandpass_filter(self, data: np.ndarray, lowcut: float, highcut: float, order: int = 4) -> np.ndarray:
        """
        Apply a zero-phase Butterworth bandpass filter.
        Supports 1D arrays (samples,) and 2D arrays (channels, samples).
        """
        nyq = 0.5 * self.sample_rate
        low = max(lowcut / nyq, 0.001)
        high = min(highcut / nyq, 0.999)

        if low >= high:
            return data

        cache_key = f"bp_{lowcut}_{highcut}_{order}_{self.sample_rate}"
        if cache_key not in self._sos_cache:
            self._sos_cache[cache_key] = signal.butter(order, [low, high], btype='band', output='sos')

        sos = self._sos_cache[cache_key]
        if data.ndim == 1:
            return signal.sosfiltfilt(sos, data).astype(data.dtype)
        else:
            return signal.sosfiltfilt(sos, data, axis=-1).astype(data.dtype)

    def notch_filter(self, data: np.ndarray, notch_freqs: List[float], quality_factor: float = 30.0) -> np.ndarray:
        """
        Apply notch (band-stop) filters at specific interference frequencies
        (e.g., 50/60 Hz power grid harmonics, specific switching frequencies).
        """
        filtered = data.copy()
        nyq = 0.5 * self.sample_rate

        for f in notch_freqs:
            if 0 < f < nyq:
                b, a = signal.iirnotch(f, quality_factor, self.sample_rate)
                if filtered.ndim == 1:
                    filtered = signal.filtfilt(b, a, filtered)
                else:
                    filtered = signal.filtfilt(b, a, filtered, axis=-1)

        return filtered.astype(data.dtype)

    def spectral_whitening(self, data: np.ndarray, eps: float = 1e-6) -> np.ndarray:
        """
        Adaptive spectral whitening to flatten colored background server noise (HVAC/fans)
        and highlight anomalous narrowband carriers.
        """
        if data.ndim == 1:
            fft_data = np.fft.rfft(data)
            mag = np.abs(fft_data) + eps
            white_fft = fft_data / mag
            return np.fft.irfft(white_fft, n=len(data)).astype(np.float32)
        else:
            # 2D multichannel
            fft_data = np.fft.rfft(data, axis=-1)
            mag = np.abs(fft_data) + eps
            white_fft = fft_data / mag
            return np.fft.irfft(white_fft, n=data.shape[-1], axis=-1).astype(np.float32)

    def remove_dc_offset(self, data: np.ndarray) -> np.ndarray:
        """Subtract mean to eliminate DC bias / LO leakage."""
        if data.ndim == 1:
            return data - np.mean(data)
        return data - np.mean(data, axis=-1, keepdims=True)
