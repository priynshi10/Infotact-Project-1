"""
Manchester Pulse Demodulator for Optical Air-Gap Covert Channels.
Filters ambient illumination flicker and decodes clock-synchronized Manchester bitstreams.
"""

import numpy as np
from scipy import signal
from typing import Dict, Any


class ManchesterOpticalDemodulator:
    """Demodulates high-speed optical LED pulses into recovered bitstreams."""

    def __init__(self, sample_rate_hz: int = 100000, bit_rate_bps: float = 1000.0):
        self.sample_rate_hz = sample_rate_hz
        self.bit_rate_bps = bit_rate_bps
        self.samples_per_bit = int(sample_rate_hz / bit_rate_bps)

    def filter_ambient_noise(self, raw_lux: np.ndarray) -> np.ndarray:
        """High-pass filter above 300 Hz to eliminate 100/120Hz room lighting interference."""
        nyquist = 0.5 * self.sample_rate_hz
        cutoff_norm = 300.0 / nyquist
        b, a = signal.butter(4, cutoff_norm, btype='highpass')
        return signal.filtfilt(b, a, raw_lux)

    def demodulate(self, filtered_signal: np.ndarray) -> Dict[str, Any]:
        """Decode Manchester bit transitions: low->high is '0', high->low is '1'."""
        threshold = np.median(filtered_signal)
        binary_levels = (filtered_signal > threshold).astype(int)

        half_bit = max(1, self.samples_per_bit // 2)
        bits = []
        i = 0
        while i + self.samples_per_bit <= len(binary_levels):
            first_half = np.mean(binary_levels[i:i + half_bit])
            second_half = np.mean(binary_levels[i + half_bit:i + self.samples_per_bit])

            if first_half < 0.5 and second_half >= 0.5:
                bits.append("0")
            elif first_half >= 0.5 and second_half < 0.5:
                bits.append("1")
            i += self.samples_per_bit

        bit_string = "".join(bits)
        is_covert_detected = len(bits) >= 4 and (float(np.ptp(filtered_signal)) > 5.0)

        return {
            "is_detected": is_covert_detected,
            "recovered_bits": bit_string,
            "peak_to_peak_lux": float(round(np.ptp(filtered_signal), 2)),
            "bit_count": len(bits)
        }
