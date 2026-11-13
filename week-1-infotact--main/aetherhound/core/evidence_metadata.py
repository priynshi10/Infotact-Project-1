"""
AetherHound Reusable Evidence Metadata & Provenance System
Generates, stores, and validates structured provenance metadata for:
- Live Hardware captures (RTL-SDR IQ & PyAudio microphone)
- Synthetic Simulation outputs (RF test bursts, acoustic fan synthesis, RPM simulation)
- Recorded Hardware captures

Enforces strict separation between physical hardware measurements and synthetic simulations.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# Canonical machine-readable source_type values
SOURCE_TYPE_LIVE_HARDWARE = "LIVE_HARDWARE"
SOURCE_TYPE_SYNTHETIC_SIMULATION = "SYNTHETIC_SIMULATION"
SOURCE_TYPE_RECORDED_HARDWARE = "RECORDED_HARDWARE"

VALID_SOURCE_TYPES = {
    SOURCE_TYPE_LIVE_HARDWARE,
    SOURCE_TYPE_SYNTHETIC_SIMULATION,
    SOURCE_TYPE_RECORDED_HARDWARE,
}

# Canonical human-readable data_source display labels
SOURCE_LABEL_MAP = {
    SOURCE_TYPE_LIVE_HARDWARE: "LIVE HARDWARE",
    SOURCE_TYPE_SYNTHETIC_SIMULATION: "SYNTHETIC SIMULATION",
    SOURCE_TYPE_RECORDED_HARDWARE: "RECORDED HARDWARE",
}

VALID_DATA_SOURCES = set(SOURCE_LABEL_MAP.values())

MODALITY_RF = "RF"
MODALITY_ACOUSTIC = "ACOUSTIC"
MODALITY_FAN_SIMULATION = "FAN_SIMULATION"
VALID_MODALITIES = {MODALITY_RF, MODALITY_ACOUSTIC, MODALITY_FAN_SIMULATION}


def generate_capture_id(prefix: str = "CAP") -> str:
    """Generate a globally unique, chronologically sortable capture ID."""
    utc_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short_uid = uuid.uuid4().hex[:8].upper()
    clean_prefix = "".join(c for c in prefix.upper() if c.isalnum()) or "CAP"
    return f"{clean_prefix}-{utc_stamp}-{short_uid}"


def normalize_source_type(source_label: str) -> Optional[str]:
    """Normalize display or enum source strings into canonical source_type."""
    if not isinstance(source_label, str):
        return None
    norm = source_label.strip().upper().replace("-", "_").replace(" ", "_")
    if norm in ("LIVE_HARDWARE", "LIVE_HARDWARE_DATA"):
        return SOURCE_TYPE_LIVE_HARDWARE
    if norm in ("SYNTHETIC_SIMULATION", "SYNTHETIC_SIMULATION_DATA", "SYNTHETIC"):
        return SOURCE_TYPE_SYNTHETIC_SIMULATION
    if norm in ("RECORDED_HARDWARE", "RECORDED_HARDWARE_DATA"):
        return SOURCE_TYPE_RECORDED_HARDWARE
    return None


def get_display_source_label(source_type: str) -> str:
    """Map canonical source_type to human-readable display label."""
    norm = normalize_source_type(source_type)
    if norm and norm in SOURCE_LABEL_MAP:
        return SOURCE_LABEL_MAP[norm]
    return "INVALID SOURCE"


def compute_file_sha256(file_path: str) -> str:
    """Compute SHA-256 hex digest of a file on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_array_sha256(arr: np.ndarray) -> str:
    """Compute SHA-256 hex digest of a NumPy array's raw bytes."""
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


def _format_timestamp(timestamp_epoch: Optional[float] = None) -> Tuple[float, str]:
    t_epoch = float(timestamp_epoch) if timestamp_epoch is not None else time.time()
    t_iso = datetime.fromtimestamp(t_epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return t_epoch, t_iso


def build_rf_metadata(
    sensor_id: str,
    source_type: str,
    center_freq_hz: float,
    sample_rate_hz: float,
    rf_gain: Any,
    sample_count: int,
    fft_size: int,
    data_file: str,
    acquisition_mode: str,
    data_sha256: str = "",
    plot_file: Optional[str] = None,
    capture_id: Optional[str] = None,
    timestamp_epoch: Optional[float] = None,
    noise_floor_db: Optional[float] = None,
    peak_freq_hz: Optional[float] = None,
    peak_power_db: Optional[float] = None,
    detector_event_type: Optional[str] = None,
    notes: str = "",
) -> Dict[str, Any]:
    """Create a complete, schema-compliant RF capture metadata dictionary."""
    norm_source = normalize_source_type(source_type) or source_type
    data_source = SOURCE_LABEL_MAP.get(norm_source, str(source_type))
    t_epoch, t_iso = _format_timestamp(timestamp_epoch)
    cap_id = capture_id or generate_capture_id("RF")
    duration_sec = float(sample_count / sample_rate_hz) if sample_rate_hz > 0 else 0.0

    return {
        "capture_id": cap_id,
        "modality": MODALITY_RF,
        "sensor_id": sensor_id,
        "source_type": norm_source,
        "data_source": data_source,
        "acquisition_mode": acquisition_mode,
        "timestamp": t_iso,
        "timestamp_epoch": t_epoch,
        "center_freq_hz": float(center_freq_hz),
        "sample_rate": float(sample_rate_hz),
        "sample_rate_hz": float(sample_rate_hz),
        "rf_gain": rf_gain,
        "fft_size": int(fft_size),
        "sample_count": int(sample_count),
        "duration_sec": duration_sec,
        "data_file": data_file,
        "data_sha256": data_sha256,
        "plot_file": plot_file or "",
        "hardware_provenance_attested": (norm_source == SOURCE_TYPE_LIVE_HARDWARE),
        "detector_event_type": detector_event_type,
        "metrics": {
            "noise_floor_db": round(float(noise_floor_db), 2) if noise_floor_db is not None else None,
            "peak_freq_hz": round(float(peak_freq_hz), 1) if peak_freq_hz is not None else None,
            "peak_power_db": round(float(peak_power_db), 2) if peak_power_db is not None else None,
        },
        "notes": notes,
    }


def build_acoustic_metadata(
    sensor_id: str,
    source_type: str,
    sample_rate_hz: int,
    channels: int,
    audio_format: str,
    sample_count: int,
    data_file: str,
    acquisition_mode: str,
    data_sha256: str = "",
    plot_file: Optional[str] = None,
    capture_id: Optional[str] = None,
    timestamp_epoch: Optional[float] = None,
    target_pattern: Optional[str] = None,
    match_score: Optional[float] = None,
    detector_event_type: Optional[str] = None,
    notes: str = "",
) -> Dict[str, Any]:
    """Create a complete, schema-compliant Acoustic recording metadata dictionary."""
    norm_source = normalize_source_type(source_type) or source_type
    data_source = SOURCE_LABEL_MAP.get(norm_source, str(source_type))
    t_epoch, t_iso = _format_timestamp(timestamp_epoch)
    cap_id = capture_id or generate_capture_id("MIC")
    duration_sec = float(sample_count / sample_rate_hz) if sample_rate_hz > 0 else 0.0

    return {
        "capture_id": cap_id,
        "modality": MODALITY_ACOUSTIC,
        "sensor_id": sensor_id,
        "source_type": norm_source,
        "data_source": data_source,
        "acquisition_mode": acquisition_mode,
        "timestamp": t_iso,
        "timestamp_epoch": t_epoch,
        "sample_rate": int(sample_rate_hz),
        "sample_rate_hz": float(sample_rate_hz),
        "channels": int(channels),
        "audio_format": str(audio_format),
        "sample_count": int(sample_count),
        "num_frames": int(sample_count),
        "duration_sec": round(duration_sec, 4),
        "data_file": data_file,
        "data_sha256": data_sha256,
        "plot_file": plot_file or "",
        "hardware_provenance_attested": (norm_source == SOURCE_TYPE_LIVE_HARDWARE),
        "detector_event_type": detector_event_type,
        "metrics": {
            "duration_sec": round(duration_sec, 2),
            "match_score": round(float(match_score), 3) if match_score is not None else 0.0,
            "target_pattern": target_pattern or "",
        },
        "notes": notes,
    }


def build_fan_simulation_metadata(
    sensor_id: str,
    sample_rate_hz: float,
    sample_count: int,
    duration_sec: float,
    data_file: str,
    simulation_parameters: Dict[str, Any],
    data_sha256: str = "",
    plot_file: Optional[str] = None,
    capture_id: Optional[str] = None,
    timestamp_epoch: Optional[float] = None,
    source_type: str = SOURCE_TYPE_SYNTHETIC_SIMULATION,
    notes: str = "",
) -> Dict[str, Any]:
    """Create schema-compliant metadata for the benign fan RPM simulation."""
    norm_source = normalize_source_type(source_type) or source_type
    data_source = SOURCE_LABEL_MAP.get(norm_source, str(source_type))
    t_epoch, t_iso = _format_timestamp(timestamp_epoch)
    cap_id = capture_id or generate_capture_id("FANSIM")

    return {
        "capture_id": cap_id,
        "modality": MODALITY_FAN_SIMULATION,
        "sensor_id": sensor_id,
        "source_type": norm_source,
        "data_source": data_source,
        "acquisition_mode": "Software Aerodynamic Simulation (No Tachometer)",
        "rpm_source": "SIMULATED" if norm_source == SOURCE_TYPE_SYNTHETIC_SIMULATION else "MEASURED",
        "tachometer_attached": False,
        "timestamp": t_iso,
        "timestamp_epoch": t_epoch,
        "sample_rate": float(sample_rate_hz),
        "sample_rate_hz": float(sample_rate_hz),
        "sample_count": int(sample_count),
        "duration_sec": round(float(duration_sec), 4),
        "data_file": data_file,
        "data_sha256": data_sha256,
        "plot_file": plot_file or "",
        "hardware_provenance_attested": False,
        "detector_event_type": "FAN_RPM_SIMULATION",
        "simulation_parameters": simulation_parameters,
        "metrics": {
            "base_rpm": simulation_parameters.get("base_rpm", 1200.0),
            "low_rpm": simulation_parameters.get("low_rpm", 900.0),
            "high_rpm": simulation_parameters.get("high_rpm", 1800.0),
            "message": simulation_parameters.get("message", "SOS"),
        },
        "notes": notes or "Benign software simulation of fan RPM trajectory. Tachometer hardware not attached.",
    }


def validate_metadata(meta: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate evidence metadata structure, required fields, types, source labels, and timestamps.
    Returns (is_valid, list_of_error_messages).
    """
    errors: List[str] = []
    if not isinstance(meta, dict):
        return False, ["Metadata payload must be a JSON object"]

    # 1. Required base fields
    required_common = [
        "capture_id",
        "sensor_id",
        "source_type",
        "data_source",
        "timestamp",
        "sample_rate",
        "sample_count",
        "data_file",
        "acquisition_mode",
    ]
    for field_name in required_common:
        val = meta.get(field_name)
        if val is None or (isinstance(val, str) and not val.strip()):
            errors.append(f"Missing required metadata field: '{field_name}'")

    # 2. Validate source_type and data_source consistency
    raw_source_type = meta.get("source_type", "")
    raw_data_source = meta.get("data_source", "")
    if raw_source_type not in VALID_SOURCE_TYPES:
        errors.append(
            f"Invalid source_type '{raw_source_type}'. Must be one of {sorted(VALID_SOURCE_TYPES)}"
        )
    else:
        expected_label = SOURCE_LABEL_MAP[raw_source_type]
        if raw_data_source != expected_label:
            errors.append(
                f"Mismatched data_source '{raw_data_source}' for source_type '{raw_source_type}' (expected '{expected_label}')"
            )

    # Guard against synthetic artifacts claiming live hardware
    sensor_id_str = str(meta.get("sensor_id", "")).upper()
    acq_mode_str = str(meta.get("acquisition_mode", "")).upper()
    if raw_source_type == SOURCE_TYPE_LIVE_HARDWARE:
        if any(tok in sensor_id_str for tok in ("SYNTHETIC", "VIRTUAL", "SIMULATOR", "SIM-")):
            errors.append(
                f"Source label conflict: source_type is LIVE_HARDWARE but sensor_id '{meta.get('sensor_id')}' indicates synthetic/simulated origin"
            )
        if any(tok in acq_mode_str for tok in ("SYNTHETIC", "SIMULATION", "SOFTWARE MODEL")):
            errors.append(
                f"Source label conflict: source_type is LIVE_HARDWARE but acquisition_mode '{meta.get('acquisition_mode')}' indicates simulation"
            )

    # 3. Validate timestamp ISO 8601 format
    ts_str = meta.get("timestamp", "")
    if isinstance(ts_str, str) and ts_str.strip():
        try:
            if ts_str.endswith("Z"):
                datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            else:
                datetime.fromisoformat(ts_str)
        except Exception:
            errors.append(f"Invalid ISO-8601 timestamp format: '{ts_str}'")

    # 4. Validate sample_rate & sample_count numeric bounds
    sr = meta.get("sample_rate")
    if sr is not None:
        try:
            if float(sr) <= 0:
                errors.append(f"sample_rate must be > 0 (got {sr})")
        except (TypeError, ValueError):
            errors.append(f"sample_rate must be numeric (got {sr})")

    sc = meta.get("sample_count")
    if sc is not None:
        try:
            if int(sc) <= 0:
                errors.append(f"sample_count must be > 0 (got {sc})")
        except (TypeError, ValueError):
            errors.append(f"sample_count must be an integer (got {sc})")

    # 5. Modality-specific required fields
    modality = meta.get("modality", "")
    if modality == MODALITY_RF:
        for rf_field in ("center_freq_hz", "rf_gain", "fft_size"):
            if meta.get(rf_field) is None or (isinstance(meta.get(rf_field), str) and not str(meta.get(rf_field)).strip()):
                errors.append(f"Missing RF metadata field: '{rf_field}'")
        if meta.get("fft_size") is not None:
            try:
                if int(meta["fft_size"]) < 64:
                    errors.append(f"Invalid RF fft_size: {meta['fft_size']}")
            except (TypeError, ValueError):
                errors.append(f"RF fft_size must be an integer (got {meta['fft_size']})")

    elif modality == MODALITY_ACOUSTIC:
        for ac_field in ("channels", "audio_format", "duration_sec"):
            if meta.get(ac_field) is None or (isinstance(meta.get(ac_field), str) and not str(meta.get(ac_field)).strip()):
                errors.append(f"Missing Acoustic metadata field: '{ac_field}'")
        if meta.get("channels") is not None:
            try:
                if int(meta["channels"]) not in (1, 2):
                    errors.append(f"Invalid acoustic channels: {meta['channels']}")
            except (TypeError, ValueError):
                errors.append(f"Acoustic channels must be integer 1 or 2")

    elif modality == MODALITY_FAN_SIMULATION:
        if raw_source_type == SOURCE_TYPE_LIVE_HARDWARE and not meta.get("tachometer_attached", False):
            errors.append("Fan simulation cannot be labeled LIVE_HARDWARE without an attached physical tachometer")
        if not isinstance(meta.get("simulation_parameters"), dict):
            errors.append("Missing or invalid 'simulation_parameters' dictionary for Fan Simulation")

    return len(errors) == 0, errors


def save_metadata(meta: Dict[str, Any], json_path: str) -> str:
    """Persist metadata dictionary cleanly to JSON file."""
    os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    return json_path


def load_metadata(json_path: str) -> Optional[Dict[str, Any]]:
    """Load metadata dictionary from JSON file."""
    if not os.path.exists(json_path):
        return None
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
