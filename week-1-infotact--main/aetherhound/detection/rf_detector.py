"""
AetherHound RF Anomaly Detector Module
Performs real-time statistical anomaly detection on live RF spectrum windows
using rolling baseline estimation, Median Absolute Deviation (MAD),
persistence tracking, and hysteresis to eliminate false alerts.
"""

from collections import deque
from dataclasses import dataclass, field
import time
from typing import Deque, Dict, List, Optional

import numpy as np

from aetherhound.dsp.rf_processor import RFProcessedWindow, SpectralPeak
from aetherhound.hardware.config import RFConfig


@dataclass
class RFAlertEvent:
    """Structured RF Anomaly Alert Event."""
    event_type: str                  # e.g. "Unusual RF Spectral Activity"
    sensor_id: str                   # "SDR-01"
    detected_freq_hz: float          # Measured center frequency of anomaly
    signal_power_db: float           # Measured power
    noise_floor_db: float            # Estimated local noise floor
    deviation_db: float              # Measured deviation above noise floor
    sigma_deviation: float           # Deviation in units of noise floor standard deviation
    persistence_windows: int         # Consecutive windows observed
    timestamp: float                 # Epoch timestamp
    status: str = "SUSPICIOUS RF ACTIVITY"
    is_synthetic: bool = False
    evidence: Dict[str, float] = field(default_factory=dict)


class RFDetector:
    """
    Real-time statistical RF anomaly detector.
    Tracks persistent spectral spikes, bursts, and anomalous deviations.
    """

    def __init__(
        self,
        config: Optional[RFConfig] = None,
        sensor_id: str = "SDR-01",
        min_persistence_windows: int = 3,
        hysteresis_cooldown_sec: float = 1.0,
    ):
        self.config = config or RFConfig()
        self.sensor_id = sensor_id
        self.min_persistence_windows = min_persistence_windows
        self.hysteresis_cooldown_sec = hysteresis_cooldown_sec

        # Rolling baseline of noise floor medians
        self._noise_medians: Deque[float] = deque(maxlen=self.config.rolling_baseline_len)
        self._noise_mads: Deque[float] = deque(maxlen=self.config.rolling_baseline_len)

        # Persistent frequency trackers: freq_bin -> count of consecutive hits
        self._active_peaks: Dict[int, int] = {}
        self._last_alert_time: float = 0.0
        self._last_event: Optional[RFAlertEvent] = None
        self._is_in_alarm: bool = False

    @property
    def last_event(self) -> Optional[RFAlertEvent]:
        return self._last_event

    def update(self, window: RFProcessedWindow) -> Optional[RFAlertEvent]:
        """
        Evaluate an incoming RFProcessedWindow for anomalies.
        Returns RFAlertEvent if a persistent, statistically significant anomaly is identified.
        """
        now = window.timestamp
        self._noise_medians.append(window.noise_floor_db)
        self._noise_mads.append(window.noise_std_db)

        # Baseline noise statistics
        baseline_noise = float(np.median(self._noise_medians))
        baseline_sigma = float(np.median(self._noise_mads))

        current_peak_bins = set()
        suspicious_peaks: List[SpectralPeak] = []

        # Evaluate peaks
        for peak in window.peaks:
            current_peak_bins.add(peak.bin_index)
            # Deviation in dB and in sigmas
            dev_db = peak.power_db - baseline_noise
            sigmas = dev_db / max(baseline_sigma, 0.5)

            # Check if exceeds threshold
            if sigmas >= self.config.detection_threshold_sigma and dev_db >= 6.0:
                # Increment persistence
                streak = self._active_peaks.get(peak.bin_index, 0) + 1
                self._active_peaks[peak.bin_index] = streak
                if streak >= self.min_persistence_windows:
                    suspicious_peaks.append(peak)
            else:
                self._active_peaks[peak.bin_index] = 0

        # Prune inactive bins
        for b in list(self._active_peaks.keys()):
            if b not in current_peak_bins:
                self._active_peaks[b] = max(0, self._active_peaks[b] - 1)
                if self._active_peaks[b] == 0:
                    del self._active_peaks[b]

        # Trigger alert if persistent anomaly found and hysteresis cooldown expired
        if suspicious_peaks:
            strongest = max(suspicious_peaks, key=lambda p: p.power_db)
            dev_db = strongest.power_db - baseline_noise
            sigmas = dev_db / max(baseline_sigma, 0.5)
            persistence = self._active_peaks.get(strongest.bin_index, self.min_persistence_windows)

            if (now - self._last_alert_time) >= self.hysteresis_cooldown_sec or not self._is_in_alarm:
                self._last_alert_time = now
                self._is_in_alarm = True

                event = RFAlertEvent(
                    event_type="Unusual RF Spectral Activity",
                    sensor_id=self.sensor_id,
                    detected_freq_hz=strongest.frequency_hz,
                    signal_power_db=round(strongest.power_db, 2),
                    noise_floor_db=round(baseline_noise, 2),
                    deviation_db=round(dev_db, 2),
                    sigma_deviation=round(sigmas, 2),
                    persistence_windows=persistence,
                    timestamp=now,
                    status="SUSPICIOUS RF ACTIVITY",
                    is_synthetic=window.is_synthetic,
                    evidence={
                        "peak_bin": strongest.bin_index,
                        "noise_std_db": round(baseline_sigma, 2),
                        "total_peaks": len(window.peaks),
                    },
                )
                self._last_event = event
                return event
        else:
            # Hysteresis reset
            if (now - self._last_alert_time) > self.hysteresis_cooldown_sec:
                self._is_in_alarm = False

        return None
