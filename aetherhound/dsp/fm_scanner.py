"""
AirHopper FM Frequency Scanner & Anomaly Detector.
Scans Software-Defined Radio (SDR) captures in the 90-110 MHz range for unauthorized
narrowband FM signal structures characteristic of video-cable RF covert leakage.
"""

import numpy as np
from typing import Dict, Any


class AirHopperDetector:
    """Analyzes SDR complex baseband samples to detect clandestine FM emissions."""

    def __init__(self, sample_rate: int = 2400000, threshold_kurtosis: float = 1.8):
        self.sample_rate = sample_rate
        self.threshold_kurtosis = threshold_kurtosis

    def detect_fm_covert_channel(self, iq_samples: np.ndarray) -> Dict[str, Any]:
        """Calculate instantaneous frequency deviation and kurtosis to detect AirHopper."""
        if len(iq_samples) < 128:
            return {"is_detected": False, "kurtosis": 0.0, "freq_dev_hz": 0.0}

        phase = np.unwrap(np.angle(iq_samples))
        inst_freq = np.diff(phase) * (self.sample_rate / (2.0 * np.pi))

        mean_freq = np.mean(inst_freq)
        var_freq = np.var(inst_freq) + 1e-12
        kurtosis = float(np.mean((inst_freq - mean_freq) ** 4) / (var_freq ** 2))
        freq_dev = float(np.std(inst_freq))

        is_detected = (kurtosis > self.threshold_kurtosis) and (freq_dev > 10000.0)

        return {
            "is_detected": is_detected,
            "kurtosis": round(kurtosis, 3),
            "freq_dev_hz": round(freq_dev, 1)
        }
