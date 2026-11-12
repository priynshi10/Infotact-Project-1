"""
AetherHound RF Signal Processor Module
Executes live FFT, power spectral density, noise floor estimation,
peak extraction, and spectral tracking for RTL-SDR windows.
"""

from collections import deque
from dataclasses import dataclass, field
import time
from typing import List, Optional, Tuple

import numpy as np
from scipy import signal

from aetherhound.dsp.fft_engine import compute_power_spectrum_db
from aetherhound.dsp.spectrogram import RollingWaterfallBuffer
from aetherhound.hardware.config import RFConfig
from aetherhound.hardware.rf_capture import IQSampleWindow


@dataclass
class SpectralPeak:
    """A detected spectral peak in the RF window."""
    frequency_hz: float
    power_db: float
    deviation_above_noise_db: float
    bin_index: int


@dataclass
class RFProcessedWindow:
    """Complete processed results for an RF window."""
    window_id: int
    timestamp: float
    center_freq_hz: float
    sample_rate_hz: float
    frequencies_hz: np.ndarray
    spectrum_db: np.ndarray
    noise_floor_db: float
    noise_std_db: float
    peaks: List[SpectralPeak]
    max_peak_freq_hz: float
    max_peak_power_db: float
    max_deviation_db: float
    is_synthetic: bool = False


class RFProcessor:
    """
    Continuous RF digital signal processor.
    Calculates windowed FFT, calibrated dB power spectrum, robust noise floor,
    and identifies spectral anomalies.
    """

    def __init__(self, config: Optional[RFConfig] = None):
        self.config = config or RFConfig()
        self.fft_size = self.config.fft_size
        self.waterfall = RollingWaterfallBuffer(max_rows=128, num_bins=min(512, self.fft_size))

        # Rolling baseline buffers for noise floor adaptation
        self._noise_floor_history = deque(maxlen=self.config.rolling_baseline_len)
        self._peak_history = deque(maxlen=50)

        # Retain latest raw IQ window and spectrum for provenance validation
        self.latest_raw_iq: Optional[np.ndarray] = None
        self.latest_frequencies_hz: Optional[np.ndarray] = None
        self.latest_spectrum_db: Optional[np.ndarray] = None
        self.latest_processed: Optional[RFProcessedWindow] = None

    def process_window(self, window: IQSampleWindow) -> RFProcessedWindow:
        """
        Process an incoming IQ sample window through the DSP pipeline.
        """
        samples = window.samples
        sr = window.sample_rate_hz
        fc = window.center_freq_hz

        # 1. FFT and Power Spectrum in dB
        freqs, power_db = compute_power_spectrum_db(
            iq_samples=samples,
            fft_size=self.fft_size,
            sample_rate_hz=sr,
            center_freq_hz=fc,
            window_type="hann",
        )

        # 2. Robust Noise Floor Estimation via Median Absolute Deviation (MAD)
        # RF signals occupy a few narrow channels; median represents the noise floor
        noise_floor_db = float(np.median(power_db))
        # Normalized MAD for normal distribution: 1.4826 * median(|x - median|)
        mad = float(np.median(np.abs(power_db - noise_floor_db)))
        noise_std_db = float(max(1.4826 * mad, 0.5))

        self._noise_floor_history.append(noise_floor_db)

        # 3. Peak Detection
        # Minimum height above noise floor (at least 3.0 * MAD or 6 dB)
        min_peak_height = noise_floor_db + max(6.0, 3.0 * noise_std_db)
        min_distance = max(4, self.fft_size // 128)

        peak_indices, properties = signal.find_peaks(
            power_db,
            height=min_peak_height,
            distance=min_distance,
            prominence=max(3.0, 2.0 * noise_std_db),
        )

        peaks: List[SpectralPeak] = []
        for idx in peak_indices:
            f_hz = float(freqs[idx])
            p_db = float(power_db[idx])
            dev_db = float(p_db - noise_floor_db)
            peaks.append(
                SpectralPeak(
                    frequency_hz=f_hz,
                    power_db=p_db,
                    deviation_above_noise_db=dev_db,
                    bin_index=int(idx),
                )
            )

        # Sort peaks descending by power
        peaks.sort(key=lambda p: p.power_db, reverse=True)

        if peaks:
            max_peak = peaks[0]
            max_freq = max_peak.frequency_hz
            max_pwr = max_peak.power_db
            max_dev = max_peak.deviation_above_noise_db
        else:
            max_idx = int(np.argmax(power_db))
            max_freq = float(freqs[max_idx])
            max_pwr = float(power_db[max_idx])
            max_dev = float(max_pwr - noise_floor_db)

        self._peak_history.append((max_freq, max_pwr, window.timestamp))

        # 4. Push to waterfall history
        self.waterfall.push_spectrum(power_db, freqs, window.timestamp)

        proc_win = RFProcessedWindow(
            window_id=window.window_id,
            timestamp=window.timestamp,
            center_freq_hz=fc,
            sample_rate_hz=sr,
            frequencies_hz=freqs,
            spectrum_db=power_db,
            noise_floor_db=noise_floor_db,
            noise_std_db=noise_std_db,
            peaks=peaks,
            max_peak_freq_hz=max_freq,
            max_peak_power_db=max_pwr,
            max_deviation_db=max_dev,
            is_synthetic=window.is_synthetic,
        )

        self.latest_raw_iq = samples
        self.latest_frequencies_hz = freqs
        self.latest_spectrum_db = power_db
        self.latest_processed = proc_win

        return proc_win
