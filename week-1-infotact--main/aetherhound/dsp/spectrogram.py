"""
AetherHound Spectrogram & Waterfall Module
Maintains thread-safe rolling buffers for live RF waterfalls and acoustic spectrograms.
"""

from collections import deque
import threading
from typing import Optional, Tuple
import numpy as np


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
