"""
Optical Photo-Diode Sensor Receiver for Air-Gap LED Covert Channel Detection.
Captures high-frequency visible and near-infrared intensity variations emitted by
compromised device status LEDs (HDD activity, Caps Lock, NIC link).
"""

import numpy as np


class OpticalReceiver:
    """Simulates high-speed photo-diode sensor telemetry capturing optical exfiltration."""

    def __init__(self, sample_rate_hz: int = 100000, ambient_lux: float = 350.0):
        self.sample_rate_hz = sample_rate_hz
        self.ambient_lux = ambient_lux

    def capture_frame(self, duration_sec: float, led_signal: np.ndarray = None) -> np.ndarray:
        """Capture ambient lighting frame mixed with optional high-frequency LED pulses."""
        total_samples = int(duration_sec * self.sample_rate_hz)
        t = np.linspace(0, duration_sec, total_samples, endpoint=False)
        mains_flicker = 15.0 * np.sin(2.0 * np.pi * 100.0 * t)
        noise = np.random.normal(0, 2.0, total_samples)
        baseline = self.ambient_lux + mains_flicker + noise

        if led_signal is not None:
            if len(led_signal) < total_samples:
                padded = np.zeros(total_samples)
                padded[:len(led_signal)] = led_signal
                return (baseline + padded).astype(np.float32)
            return (baseline + led_signal[:total_samples]).astype(np.float32)
        return baseline.astype(np.float32)
