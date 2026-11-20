"""
AetherHound Evidence Data Provenance Module
Provides cryptographically verifiable metadata tracking, SHA-256 integrity hashing,
and strict distinction between Live Hardware, Synthetic Simulation, and Recorded data.
"""

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
import os
import time
from typing import Any, Dict, Literal, Optional

import numpy as np


SourceModeType = Literal["LIVE HARDWARE", "SYNTHETIC SIMULATION", "RECORDED HARDWARE DATA"]


@dataclass
class EvidenceProvenance:
    """Cryptographic provenance record accompanying every signal plot and capture."""
    plot_path: str
    source_mode: SourceModeType
    sensor_id: str
    capture_timestamp_iso: str
    capture_timestamp_epoch: float
    sample_rate_hz: float
    center_freq_hz: Optional[float]
    recording_duration_sec: float
    sample_count: int
    raw_data_path: str
    raw_data_sha256: str
    device_verified: bool
    detection_event_type: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    capture_id: Optional[str] = None
    modality: Optional[str] = None
    source_type: Optional[str] = None
    data_source: Optional[str] = None
    acquisition_mode: Optional[str] = None
    rf_gain: Any = None
    fft_size: Optional[int] = None
    channels: Optional[int] = None
    audio_format: Optional[str] = None
    simulation_parameters: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_bytes_sha256(data: bytes) -> str:
    """Compute SHA-256 hash of raw byte buffer."""
    return hashlib.sha256(data).hexdigest()


def compute_array_sha256(arr: np.ndarray) -> str:
    """Compute deterministic SHA-256 hash of a NumPy array buffer."""
    return hashlib.sha256(arr.tobytes()).hexdigest()


def compute_file_sha256(file_path: str) -> str:
    """Compute SHA-256 hash of an existing file on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def save_provenance_metadata(prov: EvidenceProvenance, json_path: str) -> str:
    """Save provenance record to JSON file alongside plot and raw data."""
    os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(prov.to_dict(), f, indent=2)
    return json_path


def load_provenance_metadata(json_path: str) -> Optional[EvidenceProvenance]:
    """Load and validate provenance metadata, defaulting fields absent in older files."""
    if not os.path.exists(json_path):
        return None

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("Provenance metadata must be a JSON object")

    required_fields = {
        "plot_path",
        "source_mode",
        "sensor_id",
        "capture_timestamp_iso",
        "capture_timestamp_epoch",
        "sample_rate_hz",
        "center_freq_hz",
        "recording_duration_sec",
        "sample_count",
        "raw_data_path",
        "raw_data_sha256",
        "device_verified",
    }
    missing_fields = required_fields - data.keys()
    if missing_fields:
        raise ValueError(
            "Provenance metadata is missing required fields: "
            + ", ".join(sorted(missing_fields))
        )

    valid_fields = set(EvidenceProvenance.__dataclass_fields__)
    unknown_fields = data.keys() - valid_fields
    if unknown_fields:
        raise ValueError(
            "Provenance metadata has unknown fields: "
            + ", ".join(sorted(unknown_fields))
        )

    string_fields = (
        "plot_path",
        "source_mode",
        "sensor_id",
        "capture_timestamp_iso",
        "raw_data_path",
        "raw_data_sha256",
    )
    for name in string_fields:
        if not isinstance(data[name], str) or not data[name]:
            raise ValueError(f"Provenance field {name!r} must be a non-empty string")

    numeric_fields = (
        "capture_timestamp_epoch",
        "sample_rate_hz",
        "recording_duration_sec",
    )
    for name in numeric_fields:
        value = data[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"Provenance field {name!r} must be a finite number")

    center_freq_hz = data["center_freq_hz"]
    if center_freq_hz is not None and (
        isinstance(center_freq_hz, bool)
        or not isinstance(center_freq_hz, (int, float))
        or not math.isfinite(center_freq_hz)
    ):
        raise ValueError("Provenance field 'center_freq_hz' must be a finite number or null")

    if isinstance(data["sample_count"], bool) or not isinstance(data["sample_count"], int):
        raise ValueError("Provenance field 'sample_count' must be an integer")
    if not isinstance(data["device_verified"], bool):
        raise ValueError("Provenance field 'device_verified' must be a boolean")
    if "detection_event_type" in data and data["detection_event_type"] is not None and not isinstance(
        data["detection_event_type"], str
    ):
        raise ValueError("Provenance field 'detection_event_type' must be a string or null")
    if "metrics" in data and not isinstance(data["metrics"], dict):
        raise ValueError("Provenance field 'metrics' must be an object")
    if "notes" in data and not isinstance(data["notes"], str):
        raise ValueError("Provenance field 'notes' must be a string")

    optional_string_fields = (
        "capture_id",
        "modality",
        "source_type",
        "data_source",
        "acquisition_mode",
        "audio_format",
    )
    for name in optional_string_fields:
        if name in data and data[name] is not None and not isinstance(data[name], str):
            raise ValueError(f"Provenance field {name!r} must be a string or null")

    for name in ("fft_size", "channels"):
        if name in data and data[name] is not None and (
            isinstance(data[name], bool) or not isinstance(data[name], int)
        ):
            raise ValueError(f"Provenance field {name!r} must be an integer or null")

    if "simulation_parameters" in data and data["simulation_parameters"] is not None and not isinstance(
        data["simulation_parameters"], dict
    ):
        raise ValueError("Provenance field 'simulation_parameters' must be an object or null")

    return EvidenceProvenance(**data)
