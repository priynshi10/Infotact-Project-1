"""Deterministic, clearly labelled software-only signal generators."""

from dataclasses import dataclass
import os
from typing import Optional

import numpy as np
import soundfile as sf

from aetherhound.core.evidence_metadata import (
    SOURCE_TYPE_SYNTHETIC_SIMULATION,
    build_acoustic_metadata,
    build_rf_metadata,
    compute_array_sha256,
    compute_file_sha256,
    save_metadata,
    validate_metadata,
)


@dataclass
class SyntheticRFResult:
    samples: np.ndarray
    sample_rate_hz: float
    timestamp: float
    metadata: dict
    npy_path: str
    metadata_path: str


@dataclass
class SyntheticAcousticResult:
    samples: np.ndarray
    sample_rate_hz: int
    timestamp: float
    metadata: dict
    wav_path: str
    metadata_path: str


def generate_synthetic_rf(
    duration_sec: float,
    sample_rate_hz: float,
    carrier_hz: float = 150000.0,
    amplitude: float = 0.5,
    noise: float = 0.02,
    seed: int = 2026,
    output_dir: str = "data/rf/raw",
    overwrite: bool = False,
) -> SyntheticRFResult:
    if duration_sec <= 0 or sample_rate_hz <= 0:
        raise ValueError("duration_sec and sample_rate_hz must be positive")
    if amplitude < 0 or noise < 0:
        raise ValueError("amplitude and noise must be non-negative")
    if not 0 <= abs(carrier_hz) <= 0.5 * sample_rate_hz:
        raise ValueError("carrier_hz must fit within the sample-rate Nyquist range")

    import time
    timestamp = time.time()
    count = int(round(duration_sec * sample_rate_hz))
    if count < 2:
        raise ValueError("duration_sec produces fewer than two samples")
    rng = np.random.default_rng(seed)
    t = np.arange(count, dtype=np.float64) / sample_rate_hz
    samples = (
        amplitude * np.exp(2j * np.pi * carrier_hz * t)
        + noise * (rng.normal(size=count) + 1j * rng.normal(size=count))
    ).astype(np.complex64)

    os.makedirs(output_dir, exist_ok=True)
    npy_path = os.path.abspath(os.path.join(output_dir, "synthetic_rf_iq.npy"))
    metadata_path = os.path.splitext(npy_path)[0] + ".json"
    if os.path.exists(npy_path) and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {npy_path}")
    np.save(npy_path, samples)
    metadata = build_rf_metadata(
        sensor_id="SDR-SYNTHETIC-01",
        source_type=SOURCE_TYPE_SYNTHETIC_SIMULATION,
        center_freq_hz=433920000.0,
        sample_rate_hz=sample_rate_hz,
        rf_gain="SYNTHETIC",
        sample_count=count,
        fft_size=2048,
        data_file=npy_path,
        acquisition_mode="SYNTHETIC Complex IQ Generator",
        data_sha256=compute_array_sha256(samples),
        timestamp_epoch=timestamp,
        notes="SYNTHETIC/SIMULATED signal; no physical RF was captured.",
    )
    metadata["configuration"] = {
        "carrier_hz": float(carrier_hz), "amplitude": float(amplitude),
        "noise": float(noise), "seed": int(seed),
    }
    valid, errors = validate_metadata(metadata)
    if not valid:
        raise ValueError("; ".join(errors))
    save_metadata(metadata, metadata_path)
    return SyntheticRFResult(samples, sample_rate_hz, timestamp, metadata, npy_path, metadata_path)


def generate_synthetic_acoustic(
    duration_sec: float,
    sample_rate_hz: int = 44100,
    tone_hz: float = 1000.0,
    amplitude: float = 0.25,
    noise: float = 0.01,
    seed: int = 2026,
    output_dir: str = "data/acoustic/raw",
    overwrite: bool = False,
) -> SyntheticAcousticResult:
    if duration_sec <= 0 or sample_rate_hz <= 0:
        raise ValueError("duration_sec and sample_rate_hz must be positive")
    if amplitude < 0 or noise < 0:
        raise ValueError("amplitude and noise must be non-negative")
    if tone_hz < 0 or tone_hz > 0.5 * sample_rate_hz:
        raise ValueError("tone_hz must fit within the sample-rate Nyquist range")

    import time
    timestamp = time.time()
    count = int(round(duration_sec * sample_rate_hz))
    if count < 2:
        raise ValueError("duration_sec produces fewer than two samples")
    rng = np.random.default_rng(seed)
    t = np.arange(count, dtype=np.float64) / sample_rate_hz
    samples = (
        amplitude * np.sin(2 * np.pi * tone_hz * t)
        + noise * rng.normal(size=count)
    ).astype(np.float32)
    samples = np.clip(samples, -1.0, 1.0)

    os.makedirs(output_dir, exist_ok=True)
    wav_path = os.path.abspath(os.path.join(output_dir, "synthetic_acoustic.wav"))
    metadata_path = os.path.splitext(wav_path)[0] + ".json"
    if os.path.exists(wav_path) and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {wav_path}")
    sf.write(wav_path, samples, sample_rate_hz, subtype="FLOAT")
    metadata = build_acoustic_metadata(
        sensor_id="MIC-SYNTHETIC-01",
        source_type=SOURCE_TYPE_SYNTHETIC_SIMULATION,
        sample_rate_hz=sample_rate_hz,
        channels=1,
        audio_format="float32",
        sample_count=count,
        data_file=wav_path,
        acquisition_mode="SYNTHETIC Acoustic Tone Generator",
        data_sha256=compute_file_sha256(wav_path),
        timestamp_epoch=timestamp,
        notes="SYNTHETIC/SIMULATED audio; no physical microphone was used.",
    )
    metadata["configuration"] = {
        "tone_hz": float(tone_hz), "amplitude": float(amplitude),
        "noise": float(noise), "seed": int(seed),
    }
    valid, errors = validate_metadata(metadata)
    if not valid:
        raise ValueError("; ".join(errors))
    save_metadata(metadata, metadata_path)
    return SyntheticAcousticResult(samples, sample_rate_hz, timestamp, metadata, wav_path, metadata_path)
