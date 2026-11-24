"""Reusable DSP flowgraph with an optional GNU Radio backend."""

from dataclasses import dataclass
from importlib.util import find_spec
from typing import Literal, Optional

import numpy as np

from aetherhound.dsp.fft_engine import compute_real_fft, fir_lowpass_filter
from aetherhound.dsp.spectrogram import compute_stft_spectrogram


@dataclass
class FlowgraphResult:
    mode: str
    signal_type: str
    sample_rate_hz: float
    filtered_samples: np.ndarray
    frequencies_hz: np.ndarray
    spectrum_db: np.ndarray
    spectrogram_db: np.ndarray
    frame_times_sec: np.ndarray
    warning: Optional[str] = None


class SignalProcessingFlowgraph:
    """Source -> filter -> FFT/STFT -> output architecture for RF and acoustic data."""

    def __init__(
        self,
        signal_type: Literal["acoustic", "rf"] = "acoustic",
        sample_rate_hz: float = 44100.0,
        cutoff_hz: Optional[float] = None,
        fft_size: int = 2048,
        frame_size: int = 512,
        overlap: int = 256,
        prefer_gnuradio: bool = False,
    ) -> None:
        self.signal_type = signal_type
        self.sample_rate_hz = float(sample_rate_hz)
        self.cutoff_hz = cutoff_hz or (
            8000.0 if signal_type == "acoustic" else float(sample_rate_hz) * 0.25
        )
        self.fft_size = int(fft_size)
        self.frame_size = int(frame_size)
        self.overlap = int(overlap)
        self.prefer_gnuradio = prefer_gnuradio
        self._gnu_available = find_spec("gnuradio") is not None

    @property
    def backend(self) -> str:
        if self.prefer_gnuradio and self._gnu_available:
            return "GNU RADIO (DETECTED; PYTHON DSP FALLBACK EXECUTING)"
        return "PYTHON NUMPY/SCIPY FALLBACK"

    def synthetic_source(self, duration_sec: float = 1.0, noise: float = 0.02) -> np.ndarray:
        """Generate a hardware-independent acoustic or complex-RF source."""
        duration_sec = max(0.001, float(duration_sec))
        count = max(2, int(duration_sec * self.sample_rate_hz))
        t = np.arange(count, dtype=np.float64) / self.sample_rate_hz
        rng = np.random.default_rng(2026)
        if self.signal_type == "rf":
            offset = min(float(self.sample_rate_hz) * 0.1, 250000.0)
            carrier = np.exp(2j * np.pi * offset * t)
            noise_iq = noise * (rng.normal(size=count) + 1j * rng.normal(size=count))
            return (carrier + noise_iq).astype(np.complex64)

        components = (
            0.35 * np.sin(2 * np.pi * 440.0 * t)
            + 0.20 * np.sin(2 * np.pi * 880.0 * t)
            + 0.10 * np.sin(2 * np.pi * 1320.0 * t)
        )
        return (components + noise * rng.normal(size=count)).astype(np.float32)

    def process(self, samples: np.ndarray) -> FlowgraphResult:
        """Run the source samples through filtering and existing DSP modules."""
        values = np.asarray(samples)
        if values.size == 0:
            empty = np.empty(0, dtype=values.dtype)
            freqs = np.empty(0)
            return FlowgraphResult(
                self.backend,
                self.signal_type,
                self.sample_rate_hz,
                empty,
                freqs,
                np.empty(0),
                np.empty((0, 0)),
                np.empty(0),
                "Empty input: no samples were processed",
            )
        if values.ndim != 1:
            raise ValueError("Samples must be a one-dimensional array")
        if not np.isfinite(self.sample_rate_hz) or self.sample_rate_hz <= 0:
            raise ValueError("Sample rate must be positive")

        filtered = fir_lowpass_filter(
            values,
            self.sample_rate_hz,
            self.cutoff_hz,
            numtaps=101,
        )

        if np.iscomplexobj(filtered):
            from aetherhound.dsp.fft_engine import compute_power_spectrum_db

            freqs, spectrum = compute_power_spectrum_db(
                filtered,
                fft_size=self.fft_size,
                sample_rate_hz=self.sample_rate_hz,
                center_freq_hz=0.0,
            )
        else:
            freqs, spectrum = compute_real_fft(
                filtered,
                fft_size=self.fft_size,
                sample_rate_hz=self.sample_rate_hz,
            )

        stft_freqs, times, stft_db = compute_stft_spectrogram(
            filtered,
            self.sample_rate_hz,
            nperseg=min(self.frame_size, len(filtered)),
            noverlap=min(self.overlap, min(self.frame_size, len(filtered)) - 1),
        )
        if np.iscomplexobj(filtered):
            freqs = stft_freqs

        warning = None
        if self.prefer_gnuradio and self._gnu_available:
            warning = "GNU Radio was detected but this runtime executes the Python NumPy/SciPy fallback."
        return FlowgraphResult(
            self.backend,
            self.signal_type,
            self.sample_rate_hz,
            filtered,
            freqs,
            spectrum,
            stft_db,
            times,
            warning,
        )
