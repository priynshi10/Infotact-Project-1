"""
AetherHound Acoustic Anomaly Detector Module
Performs real-time anomaly detection for acoustic channels:
tracks unexpected repetitive pulses, fan-speed modulation, sudden energy bursts,
and structured acoustic sequences.
"""

from collections import deque
from dataclasses import dataclass, field
import time
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np

from aetherhound.dsp.acoustic_processor import AcousticProcessedChunk
from aetherhound.hardware.config import AcousticConfig


@dataclass
class AcousticAlertEvent:
    """Structured Acoustic Anomaly Alert Event."""
    event_type: str                   # e.g. "Structured Acoustic Pattern Detected"
    sensor_id: str                    # "MIC-01"
    dominant_frequency_hz: float      # Measured frequency
    rms_energy: float                 # Measured RMS energy
    pulse_count: int                  # Detected pulse count
    pattern_duration_sec: float       # Duration of suspicious pattern
    timestamp: float                  # Epoch timestamp
    status: str = "SUSPICIOUS ACOUSTIC ACTIVITY"
    is_synthetic: bool = False
    evidence: Dict[str, float] = field(default_factory=dict)


class AcousticDetector:
    """
    Real-time acoustic covert channel detector.
    Analyzes energy spikes, repetition regularity, pulse intervals,
    and fan acoustic modulation.
    """

    def __init__(
        self,
        config: Optional[AcousticConfig] = None,
        sensor_id: str = "MIC-01",
        history_len: int = 40,
        hysteresis_cooldown_sec: float = 1.2,
    ):
        self.config = config or AcousticConfig()
        self.sensor_id = sensor_id
        self.history_len = history_len
        self.hysteresis_cooldown_sec = hysteresis_cooldown_sec

        # Rolling chunk history: (timestamp, rms, dominant_freq, periodicity, is_above_thresh)
        self._history: Deque[Tuple[float, float, float, float, bool]] = deque(maxlen=history_len)
        self._last_alert_time: float = 0.0
        self._last_event: Optional[AcousticAlertEvent] = None
        self._is_in_alarm: bool = False

    @property
    def last_event(self) -> Optional[AcousticAlertEvent]:
        return self._last_event

    def update(self, chunk: AcousticProcessedChunk) -> Optional[AcousticAlertEvent]:
        """
        Evaluate an incoming AcousticProcessedChunk for anomalous patterns.
        """
        now = chunk.timestamp
        rms = chunk.features.rms_energy
        dom_freq = chunk.features.dominant_frequency_hz
        periodicity = chunk.features.periodicity_score
        baseline = chunk.baseline_energy

        # Pulse state: true if energy exceeds configured baseline factor
        is_pulse_active = (chunk.energy_ratio >= self.config.energy_threshold_factor) and (rms > 0.005)

        self._history.append((now, rms, dom_freq, periodicity, is_pulse_active))

        if len(self._history) < 12:
            return None

        # Analyze rolling history for structured repetitive pulses or sustained periodic modulation
        pulse_flags = [item[4] for item in self._history]
        timestamps = [item[0] for item in self._history]
        periodicities = [item[3] for item in self._history]

        # Count pulse transitions (rising edges: False -> True)
        transitions = sum(1 for i in range(1, len(pulse_flags)) if not pulse_flags[i - 1] and pulse_flags[i])
        active_pulse_chunks = sum(1 for p in pulse_flags if p)
        mean_periodicity = float(np.mean(periodicities))

        pattern_duration = timestamps[-1] - timestamps[0]

        # Condition 1: Multiple discrete pulses occurring in window (repetitive bursts)
        repetitive_bursts = (transitions >= 3) and (active_pulse_chunks >= 3)
        # Condition 2: Sustained strong periodic modulation (such as PWM fan acoustic frequency shift)
        sustained_modulation = (mean_periodicity > 0.45) and (chunk.energy_ratio > 1.8)

        if (repetitive_bursts or sustained_modulation) and (now - self._last_alert_time >= self.hysteresis_cooldown_sec):
            self._last_alert_time = now
            self._is_in_alarm = True

            event_type = (
                "Structured Acoustic Repetitive Pulses"
                if repetitive_bursts
                else "Periodic Acoustic Modulation Detected"
            )

            event = AcousticAlertEvent(
                event_type=event_type,
                sensor_id=self.sensor_id,
                dominant_frequency_hz=round(dom_freq, 1),
                rms_energy=round(rms, 5),
                pulse_count=transitions if repetitive_bursts else active_pulse_chunks,
                pattern_duration_sec=round(pattern_duration, 2),
                timestamp=now,
                status="SUSPICIOUS ACOUSTIC ACTIVITY",
                is_synthetic=chunk.is_synthetic,
                evidence={
                    "energy_ratio": round(chunk.energy_ratio, 2),
                    "mean_periodicity": round(mean_periodicity, 3),
                    "baseline_rms": round(baseline, 5),
                    "spectral_centroid_hz": round(chunk.features.spectral_centroid_hz, 1),
                },
            )
            self._last_event = event
            return event

        if now - self._last_alert_time > self.hysteresis_cooldown_sec:
            self._is_in_alarm = False

        return None
