"""
AetherHound Acoustic Signal Processor Module
Executes audio filtering, RMS energy, spectral centroid, dominant frequency,
spectrogram update, and envelope tracking for incoming microphone chunks.
"""

from collections import deque
from dataclasses import dataclass
import time
from typing import Optional, Tuple

import numpy as np
from scipy import signal

from aetherhound.dsp.feature_extractor import (
    AcousticFeatures,
    StreamingEnvelopeFollower,
    extract_acoustic_features,
    extract_signal_envelope,
)
from aetherhound.dsp.spectrogram import RollingWaterfallBuffer, compute_stft_spectrogram
from aetherhound.hardware.acoustic_capture import AudioChunk
from aetherhound.hardware.config import AcousticConfig


@dataclass
class AcousticProcessedChunk:
    """Complete processed results for an audio chunk."""
    chunk_id: int
    timestamp: float
    sample_rate_hz: int
    raw_samples: np.ndarray
    filtered_samples: np.ndarray
    envelope: np.ndarray
    features: AcousticFeatures
    baseline_energy: float
    energy_ratio: float
    is_synthetic: bool = False
    source_type: Optional[str] = None


class AcousticProcessor:
    """
    Continuous acoustic digital signal processor.
    Applies adaptive filtering, feature extraction, STFT spectrogram updates,
    and maintains a rolling baseline of acoustic energy.
    """

    def __init__(self, config: Optional[AcousticConfig] = None):
        self.config = config or AcousticConfig()
        self.spectrogram = RollingWaterfallBuffer(max_rows=128, num_bins=256)
        self._baseline_energy_history = deque(maxlen=self.config.rolling_baseline_len)
        self._envelope_follower = StreamingEnvelopeFollower(self.config.sample_rate_hz)
        self._filter_state = None

        # Design bandpass filter: preserves typical fan blade frequencies & harmonics (50 Hz - 8000 Hz)
        nyq = 0.5 * self.config.sample_rate_hz
        low = max(20.0, 50.0) / nyq
        high = min(0.95, 8000.0 / nyq)
        self._filter_b, self._filter_a = signal.butter(2, [low, high], btype="bandpass")

        # Retain latest raw audio and envelope for provenance validation
        self.latest_raw_samples: Optional[np.ndarray] = None
        self.latest_envelope: Optional[np.ndarray] = None
        self.latest_processed: Optional[AcousticProcessedChunk] = None

    def process_chunk(self, chunk: AudioChunk) -> AcousticProcessedChunk:
        """
        Process an incoming audio chunk through filtering and feature extraction.
        """
        samples = chunk.samples
        sr = chunk.sample_rate_hz
        if len(np.asarray(samples)) == 0:
            features = AcousticFeatures(
                rms_energy=0.0,
                peak_amplitude=0.0,
                dominant_frequency_hz=0.0,
                spectral_centroid_hz=0.0,
                spectral_bandwidth_hz=0.0,
                zero_crossing_rate=0.0,
                periodicity_score=0.0,
                snr_estimate_db=0.0,
            )
            return AcousticProcessedChunk(
                chunk_id=chunk.chunk_id,
                timestamp=chunk.timestamp,
                sample_rate_hz=sr,
                raw_samples=np.asarray(samples).copy(),
                filtered_samples=np.asarray(samples).copy(),
                envelope=np.zeros(0, dtype=np.float32),
                features=features,
                baseline_energy=0.0,
                energy_ratio=0.0,
                is_synthetic=chunk.is_synthetic,
                source_type=chunk.source_type,
            )

        # 1. Bandpass filter to suppress low rumble and ultra-high hiss
        try:
            filtered = signal.lfilter(self._filter_b, self._filter_a, samples)
        except Exception:
            filtered = np.asarray(samples).copy()

        # 2. Extract acoustic features
        features = extract_acoustic_features(filtered, sr, fft_size=min(len(filtered), 2048))

        # 3. Continuous causal streaming envelope extraction
        envelope = self._envelope_follower.process(filtered)

        # 4. Rolling baseline calculation
        if len(self._baseline_energy_history) > 0:
            baseline = float(np.median(self._baseline_energy_history))
        else:
            baseline = max(features.rms_energy, 1e-6)

        # Update baseline (only if current energy is not an explosive burst)
        if len(self._baseline_energy_history) < 5 or features.rms_energy < baseline * 2.5:
            self._baseline_energy_history.append(features.rms_energy)

        # Ratio of current RMS to normal baseline
        energy_ratio = float(features.rms_energy / max(baseline, 1e-6))

        # 5. Compute STFT and push each time frame into the waterfall
        freqs, frame_times, spec_matrix_db = compute_stft_spectrogram(
            filtered,
            sr,
            nperseg=512,
            noverlap=256,
        )

        for frame_index, frame_time in enumerate(frame_times):
            self.spectrogram.push_spectrum(
                spec_matrix_db[:, frame_index],
                freqs,
                chunk.timestamp + float(frame_time),
            )

        res = AcousticProcessedChunk(
            chunk_id=chunk.chunk_id,
            timestamp=chunk.timestamp,
            sample_rate_hz=sr,
            raw_samples=samples,
            filtered_samples=filtered,
            envelope=envelope,
            features=features,
            baseline_energy=baseline,
            energy_ratio=energy_ratio,
            is_synthetic=chunk.is_synthetic,
            source_type=chunk.source_type,
        )

        self.latest_raw_samples = samples
        self.latest_envelope = envelope
        self.latest_processed = res

        return res

