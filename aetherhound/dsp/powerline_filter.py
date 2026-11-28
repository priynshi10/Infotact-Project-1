"""
Powerline Sideband Filter & Conducted Emission Detector.
High-pass filters 50Hz/60Hz AC mains energy to reveal high-frequency CPU power bursts.
"""

import numpy as np
from scipy import signal
from typing import Dict, Any


class PowerlineSidebandFilter:
    """Filters low-frequency mains current to isolate conducted PowerHammer bursts."""

    def __init__(self, sample_rate_hz: int = 10000, cutoff_hz: float = 150.0):
        self.sample_rate_hz = sample_rate_hz
        self.cutoff_hz = cutoff_hz

    def filter_mains(self, current_waveform: np.ndarray) -> np.ndarray:
        """High-pass filter above 150Hz to reject 50Hz fundamental and 100Hz 2nd harmonic."""
        nyquist = 0.5 * self.sample_rate_hz
        b, a = signal.butter(4, self.cutoff_hz / nyquist, btype='highpass')
        return signal.filtfilt(b, a, current_waveform)

    def detect_conducted_bursts(self, current_waveform: np.ndarray, threshold_rms: float = 0.3) -> Dict[str, Any]:
        """Detect anomalous high-frequency energy on electrical lines."""
        filtered = self.filter_mains(current_waveform)
        rms_energy = float(np.sqrt(np.mean(filtered ** 2)))
        peak_amp = float(np.max(np.abs(filtered)))
        is_detected = rms_energy > threshold_rms

        return {
            "is_detected": is_detected,
            "sideband_rms_amps": round(rms_energy, 4),
            "peak_sideband_amps": round(peak_amp, 4)
        }
