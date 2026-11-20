"""
AetherHound Spectrogram & Waterfall Module
Maintains thread-safe rolling buffers for live RF waterfalls and acoustic spectrograms.
"""

from collections import deque
import threading
from typing import Optional, Tuple
import numpy as np
from scipy import signal
class RollingWaterfallBuffer:
    """
    Fixed-memory rolling waterfall history for 2D spectral visualization.
    Maintains a rolling matrix of (time_steps, frequency_bins).
    """

    def __init__(self, max_rows: int = 128, num_bins: int = 512):
        self.max_rows = max_rows
        self.num_bins = num_bins
        self._buffer = deque(maxlen=max_rows)
        self._timestamps = deque(maxlen=max_rows)
        self._lock = threading.Lock()
        self._frequencies: Optional[np.ndarray] = None

    def push_spectrum(
        self,
        spectrum_db: np.ndarray,
        frequencies_hz: np.ndarray,
        timestamp: float,
    ) -> None:
        """Add a new processed spectral row to the waterfall."""
        # Resample or slice to num_bins if needed
        if len(spectrum_db) != self.num_bins:
            indices = np.linspace(0, len(spectrum_db) - 1, self.num_bins).astype(int)
            decimated_spectrum = spectrum_db[indices]
            decimated_freqs = frequencies_hz[indices]
        else:
            decimated_spectrum = spectrum_db
            decimated_freqs = frequencies_hz

        with self._lock:
            self._buffer.append(decimated_spectrum.copy())
            self._timestamps.append(timestamp)
            self._frequencies = decimated_freqs.copy()

    def get_waterfall_matrix(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Returns (matrix, frequencies_hz, timestamps).
        Matrix shape: (num_rows, num_bins), ordered oldest to newest.
        """
        with self._lock:
            if not self._buffer:
                freqs = self._frequencies if self._frequencies is not None else np.zeros(self.num_bins)
                return np.zeros((1, self.num_bins)), freqs, np.zeros(1)

            mat = np.array(list(self._buffer))
            times = np.array(list(self._timestamps))
            freqs = self._frequencies.copy() if self._frequencies is not None else np.zeros(self.num_bins)
            return mat, freqs, times

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()
            self._timestamps.clear()

def compute_stft_spectrogram(
    samples: np.ndarray,
    sample_rate_hz: float,
    nperseg: int = 512,
    noverlap: Optional[int] = None,
    window: str = "hann",
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute an STFT spectrogram for real or complex signals.

    Returns:
        frequencies_hz: Frequency bins in Hz.
        times_sec: Time bins in seconds.
        magnitude_db: Spectrogram matrix (frequency_bins, time_frames).
    """
    samples = np.asarray(samples)

    if samples.ndim != 1:
        raise ValueError("Samples must be a one-dimensional array")

    if len(samples) < 2:
        raise ValueError("At least two samples are required")

    if sample_rate_hz <= 0:
        raise ValueError("Sample rate must be positive")

    if nperseg < 2:
        raise ValueError("nperseg must be at least 2")

    nperseg = min(nperseg, len(samples))

    if noverlap is None:
        noverlap = nperseg // 2

    if noverlap < 0 or noverlap >= nperseg:
        raise ValueError("noverlap must be between 0 and nperseg - 1")

    is_complex = np.iscomplexobj(samples)

    frequencies_hz, times_sec, stft_values = signal.stft(
        samples,
        fs=sample_rate_hz,
        window=window,
        nperseg=nperseg,
        noverlap=noverlap,
        return_onesided=not is_complex,
        boundary=None,
        padded=False,
    )

    if is_complex:
        frequencies_hz = np.fft.fftshift(frequencies_hz)
        stft_values = np.fft.fftshift(stft_values, axes=0)

    magnitude = np.abs(stft_values)
    magnitude_db = 20.0 * np.log10(np.maximum(magnitude, 1e-12))

    return frequencies_hz, times_sec, magnitude_db


