"""
AetherHound Evidence Data Provenance Module
Provides cryptographically verifiable metadata tracking, SHA-256 integrity hashing,
and strict distinction between Live Hardware, Synthetic Simulation, and Recorded data.
"""

from dataclasses import asdict, dataclass, field
import hashlib
import json
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
    """Load and parse provenance record from JSON file."""
    if not os.path.exists(json_path):
        return None
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return EvidenceProvenance(**data)
    except Exception:
        return None
