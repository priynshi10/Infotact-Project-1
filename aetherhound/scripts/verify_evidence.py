#!/usr/bin/env python3
"""
AetherHound Evidence & Data Provenance Validation Script (Day 2 Upgrade)
Backward-compatible evidence verifier supporting both legacy and new Day 1+ metadata schemas,
strict cross-platform path resolution, rigorous integrity validation, source classification,
and non-destructive audit report generation.

Distinguishes:
1. File-Integrity Validation (PASS / FAIL / MISSING) & overall record status
   (VERIFIED / PARTIALLY VERIFIED / INVALID)
2. Metadata Validity & Legacy/New Field Compatibility
3. Source Classification (LIVE_HARDWARE / RECORDED_HARDWARE / SYNTHETIC_SIMULATION / UNKNOWN / INVALID)
4. Hardware Provenance Assurance (runtime-attested vs simulation; file hashes prove file integrity only,
   not independent physical hardware origin).
"""

import argparse
import csv
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import glob
import json
import math
import os
from pathlib import Path
import posixpath
import re
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf

# Ensure project root is in sys.path regardless of CWD
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# Also support execution from aetherhound/scripts/
ALT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if os.path.isdir(os.path.join(ALT_ROOT, "aetherhound")) and ALT_ROOT not in sys.path:
    sys.path.insert(0, ALT_ROOT)

from aetherhound.core.evidence_metadata import (  # noqa: E402
    MODALITY_ACOUSTIC,
    MODALITY_FAN_SIMULATION,
    MODALITY_RF,
    SOURCE_LABEL_MAP,
    SOURCE_TYPE_LIVE_HARDWARE,
    SOURCE_TYPE_RECORDED_HARDWARE,
    SOURCE_TYPE_SYNTHETIC_SIMULATION,
    compute_array_sha256,
    compute_file_sha256,
    normalize_source_type,
)

try:
    from rich.console import Console
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


_SHA256_HEX_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_WIN_DRIVE_RE = re.compile(r"^([A-Za-z]):(.*)$")


@dataclass
class EvidenceValidationRecord:
    """Preserved PlotAuditResult / EvidenceValidationRecord structure with Day 2 compatibility details."""

    capture_id: str
    modality: str                 # RF, ACOUSTIC, FAN_SIMULATION, ORPHAN_PLOT, UNKNOWN
    plot_name: str
    plot_path: str
    metadata_found: bool
    metadata_valid: bool
    metadata_path: Optional[str]
    source_type: str              # LIVE_HARDWARE, RECORDED_HARDWARE, SYNTHETIC_SIMULATION, UNKNOWN, INVALID
    source_mode: str              # LIVE HARDWARE, RECORDED HARDWARE, SYNTHETIC SIMULATION, UNKNOWN, INVALID
    sensor_id: str
    acquisition_mode: str
    capture_timestamp_iso: str
    sample_rate_hz: float
    sample_count_recorded: int
    raw_data_path: str
    raw_data_exists: bool
    raw_data_type: str
    hash_verified: bool
    recorded_sha256: str
    computed_sha256: str
    samples_verified: bool
    actual_samples: int
    timestamp_verified: bool
    validation_status: str        # VERIFIED, PARTIALLY VERIFIED, INVALID
    hardware_provenance_note: str
    failure_reasons: List[str]
    warnings: List[str]
    # Additive Day 2 fields (optional for backward compatibility)
    schema_compatibility: str = "NEW_SCHEMA"
    file_integrity_status: str = "FAIL"       # PASS, FAIL, MISSING
    source_classification: str = "INVALID"    # LIVE_HARDWARE, RECORDED_HARDWARE, SYNTHETIC_SIMULATION, UNKNOWN, INVALID
    hardware_provenance_assurance: str = "UNTRUSTED"
    sample_rate_verification: str = "UNAVAILABLE"  # VERIFIED, MISMATCH, UNAVAILABLE, INVALID_METADATA
    sha256_verification_status: str = "MISSING_EXPECTED_HASH"
    timestamp_epoch: Optional[float] = None
    path_resolution_method: str = "NOT_FOUND"
    metadata_inconsistencies: List[str] = field(default_factory=list)


# Backward-compatible alias referenced in external tools / specs
PlotAuditResult = EvidenceValidationRecord


def _normalize_slashes_and_dotdot(raw_path: str) -> Tuple[str, str]:
    """
    Safely convert Windows backslashes to forward slashes and collapse '.' / '..'
    without dropping Windows drive letters. Returns (drive_prefix, normalized_posix_part).
    """
    cleaned = raw_path.strip().replace("\\", "/")
    win_match = _WIN_DRIVE_RE.match(cleaned)
    if win_match:
        drive = f"{win_match.group(1).upper()}:"
        rest = win_match.group(2)
        if not rest.startswith("/"):
            rest = "/" + rest
        norm_rest = posixpath.normpath(rest)
        return drive, norm_rest
    norm_rest = posixpath.normpath(cleaned)
    return "", norm_rest


def _extract_structural_suffixes(norm_path: str) -> List[str]:
    """
    Extract structural project-relative suffixes from normalized paths without matching bare filenames.
    For example:
      '/app/aetherhound/data/rf/raw/capture.npy' -> ['aetherhound/data/rf/raw/capture.npy', 'data/rf/raw/capture.npy']
      'P:/project/data/rf/raw/capture.npy'       -> ['data/rf/raw/capture.npy']
    """
    parts = [p for p in norm_path.split("/") if p and p != "."]
    suffixes: List[str] = []

    # Check structural markers only when followed by deeper subpath segments (at least 2 components, not bare filename)
    for idx, part in enumerate(parts):
        lower_part = part.lower()
        if lower_part == "aetherhound" and idx + 1 < len(parts):
            tail = parts[idx:]
            suffixes.append("/".join(tail))  # aetherhound/...
            if idx + 2 < len(parts) and parts[idx + 1].lower() == "data":
                suffixes.append("/".join(parts[idx + 1:]))  # data/...
        elif lower_part == "data" and idx + 2 < len(parts):
            suffixes.append("/".join(parts[idx:]))  # data/<modality>/...

    # Deduplicate preserving order
    seen = set()
    unique: List[str] = []
    for s in suffixes:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def resolve_evidence_path(
    path_str: str,
    base_dir: str,
    data_dir: str,
    meta_dir: Optional[str] = None,
) -> Tuple[str, bool, str]:
    """
    Cross-platform path resolver supporting:
    - Windows absolute paths (P:/project/aetherhound/data/... or P:\\project\\...)
    - Linux absolute paths (/app/aetherhound/data/...)
    - Relative & project-root-relative paths (aetherhound/data/..., data/..., ../raw/...)
    - Normalized '.' and '..' components
    - Cross-OS paths evaluated against the actual project root (without matching unrelated basenames).

    Returns (resolved_path, exists, resolution_method).
    """
    if not path_str or not isinstance(path_str, str) or not path_str.strip():
        return "", False, "EMPTY"

    raw = path_str.strip()
    drive, norm_posix = _normalize_slashes_and_dotdot(raw)
    is_win_abs = bool(drive) or raw.replace("\\", "/").startswith("//")
    is_posix_abs = (not drive) and norm_posix.startswith("/")

    resolved_base = os.path.abspath(base_dir)
    resolved_data = os.path.abspath(data_dir)
    parent_base = os.path.dirname(resolved_base)

    # Build ordered anchor roots (never rely blindly on CWD or bare filenames)
    anchor_roots: List[Tuple[str, str]] = [
        (resolved_base, "PROJECT_ROOT_RELATIVE"),
        (os.path.join(resolved_base, "aetherhound"), "AETHERHOUND_ROOT_RELATIVE"),
        (resolved_data, "DATA_DIR_RELATIVE"),
    ]
    if os.path.basename(resolved_data) == "data":
        anchor_roots.append((os.path.dirname(resolved_data), "DATA_PARENT_RELATIVE"))
    if os.path.basename(resolved_base) == "aetherhound":
        anchor_roots.append((parent_base, "WORKSPACE_PARENT_RELATIVE"))
    if meta_dir:
        anchor_roots.insert(1, (os.path.abspath(meta_dir), "METADATA_DIR_RELATIVE"))

    # 1. If native OS absolute path matches directly on this host, accept exact hit first
    if os.path.isabs(raw):
        native_norm = os.path.normpath(raw)
        if os.path.exists(native_norm):
            return os.path.abspath(native_norm), True, "ABSOLUTE_EXACT"

    # 2. If relative path (neither Windows drive path nor POSIX leading '/'), check strictly against anchors
    if not is_win_abs and not is_posix_abs:
        rel_parts = [p for p in norm_posix.split("/") if p and p != "."]
        if rel_parts:
            for root_dir, method_tag in anchor_roots:
                candidate = os.path.normpath(os.path.join(root_dir, *rel_parts))
                if os.path.exists(candidate):
                    return os.path.abspath(candidate), True, method_tag

            # Also handle 'aetherhound/...' when root_dir is already '.../aetherhound'
            if rel_parts[0].lower() == "aetherhound" and len(rel_parts) > 1:
                stripped = rel_parts[1:]
                for root_dir, method_tag in anchor_roots:
                    if os.path.basename(root_dir).lower() == "aetherhound" or os.path.isdir(os.path.join(root_dir, "data")):
                        candidate = os.path.normpath(os.path.join(root_dir, *stripped))
                        if os.path.exists(candidate):
                            return os.path.abspath(candidate), True, f"{method_tag}_STRIPPED_PKG"

    # 3. Cross-machine / cross-OS anchored structural suffix resolution
    #    (e.g. 'P:/project/aetherhound/data/rf/raw/cap.npy' -> 'data/rf/raw/cap.npy' under project root)
    suffixes = _extract_structural_suffixes(norm_posix)
    for suf in suffixes:
        suf_parts = suf.split("/")
        for root_dir, method_tag in anchor_roots:
            candidate = os.path.normpath(os.path.join(root_dir, *suf_parts))
            if os.path.exists(candidate):
                prefix = "WINDOWS_TO_LOCAL" if is_win_abs else ("LINUX_TO_LOCAL" if is_posix_abs else "ANCHORED_SUFFIX")
                return os.path.abspath(candidate), True, f"{prefix}:{method_tag}"

        # Special handling when suffix is 'data/<...>' and resolved_data itself is a custom data dir
        if suf_parts[0].lower() == "data" and len(suf_parts) > 1:
            candidate = os.path.normpath(os.path.join(resolved_data, *suf_parts[1:]))
            if os.path.exists(candidate):
                prefix = "WINDOWS_TO_LOCAL" if is_win_abs else ("LINUX_TO_LOCAL" if is_posix_abs else "ANCHORED_SUFFIX")
                return os.path.abspath(candidate), True, f"{prefix}:DATA_DIR_TAIL"

    display_unresolved = f"{drive}{norm_posix}" if drive else norm_posix
    return display_unresolved, False, "NOT_FOUND"


def _resolve_path(path_str: str, base_dir: str, data_dir: str, meta_dir: Optional[str] = None) -> str:
    """Backward-compatible wrapper returning the resolved path string."""
    resolved, _, _ = resolve_evidence_path(path_str, base_dir, data_dir, meta_dir=meta_dir)
    return resolved


def _determine_hardware_provenance_note(
    source_type: str,
    validation_status: str,
    inconsistent: bool = False,
) -> str:
    if inconsistent or validation_status == "INVALID":
        return "INVALID: Integrity, schema, or provenance consistency check failed; origin cannot be trusted."
    if source_type == SOURCE_TYPE_SYNTHETIC_SIMULATION:
        return "SYNTHETIC SIMULATION: File integrity verified; data originated from software simulation (not physical hardware)."
    if source_type == SOURCE_TYPE_LIVE_HARDWARE:
        return (
            "LIVE HARDWARE (RUNTIME ATTESTED ONLY): File integrity verified on disk, which proves hash consistency only — "
            "it cannot independently prove physical hardware acquisition without cryptographic device signing."
        )
    if source_type == SOURCE_TYPE_RECORDED_HARDWARE:
        return (
            "RECORDED HARDWARE (NOT LIVE ACQUISITION): File integrity verified on disk for previously recorded data; "
            "physical hardware origin depends on the upstream capture chain."
        )
    return "UNKNOWN / UNVERIFIED SOURCE: Source classification missing or unrecognized; never classified as hardware."


def _determine_provenance_assurance(source_type: str, validation_status: str) -> str:
    if validation_status == "INVALID" or source_type not in (
        SOURCE_TYPE_LIVE_HARDWARE,
        SOURCE_TYPE_RECORDED_HARDWARE,
        SOURCE_TYPE_SYNTHETIC_SIMULATION,
    ):
        return "UNTRUSTED"
    if source_type == SOURCE_TYPE_SYNTHETIC_SIMULATION:
        return "SOFTWARE_SIMULATION"
    if source_type == SOURCE_TYPE_RECORDED_HARDWARE:
        return "RECORDED_HARDWARE_UNATTESTED"
    if source_type == SOURCE_TYPE_LIVE_HARDWARE:
        return "RUNTIME_ATTESTED_NOT_CRYPTO_PROVEN"
    return "UNTRUSTED"


def _parse_iso_timestamp(ts_str: str) -> Tuple[Optional[datetime], bool, Optional[str]]:
    """
    Parse ISO-8601 timestamp safely handling 'Z', explicit timezone offsets, and naive datetimes.
    Never falls back to current time. Returns (datetime_obj, is_tz_aware, error_message).
    """
    if not isinstance(ts_str, str) or not ts_str.strip():
        return None, False, "Empty ISO timestamp"
    s = ts_str.strip()
    try:
        if s.endswith(("Z", "z")):
            dt = datetime.fromisoformat(s[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(s)
        is_aware = dt.tzinfo is not None and dt.utcoffset() is not None
        return dt, is_aware, None
    except Exception as e:
        return None, False, f"Invalid ISO-8601 timestamp '{ts_str}': {e}"


def _parse_epoch_timestamp(val: Any, field_name: str) -> Tuple[Optional[float], Optional[str]]:
    if isinstance(val, bool):
        return None, f"{field_name} must be numeric, not boolean"
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None, f"{field_name} must be numeric (got {val!r})"
    if not math.isfinite(f) or f <= 0:
        return None, f"{field_name} must be finite and > 0 (got {val!r})"
    return f, None


def _is_present(meta: Dict[str, Any], key: str) -> bool:
    if key not in meta:
        return False
    val = meta[key]
    if val is None:
        return False
    if isinstance(val, str) and not val.strip():
        return False
    return True


def _paths_conflict(p_new: str, p_old: str, base_dir: str, data_dir: str, meta_dir: Optional[str]) -> bool:
    """Return True if two path fields refer to genuinely different files."""
    if p_new.strip().replace("\\", "/") == p_old.strip().replace("\\", "/"):
        return False

    res_new, ex_new, _ = resolve_evidence_path(p_new, base_dir, data_dir, meta_dir=meta_dir)
    res_old, ex_old, _ = resolve_evidence_path(p_old, base_dir, data_dir, meta_dir=meta_dir)
    if ex_new and ex_old:
        return os.path.realpath(res_new) != os.path.realpath(res_old)

    # Compare structural suffix or basename if unresolved on disk
    _, norm_new = _normalize_slashes_and_dotdot(p_new)
    _, norm_old = _normalize_slashes_and_dotdot(p_old)
    suf_new = _extract_structural_suffixes(norm_new)
    suf_old = _extract_structural_suffixes(norm_old)
    if suf_new and suf_old:
        return not bool(set(suf_new) & set(suf_old))
    return posixpath.basename(norm_new) != posixpath.basename(norm_old) or norm_new != norm_old


def _infer_modality(meta: Dict[str, Any], meta_path: str) -> str:
    modality = str(meta.get("modality") or "").strip().upper()
    if modality in (MODALITY_RF, MODALITY_ACOUSTIC, MODALITY_FAN_SIMULATION):
        return modality
    norm_path = meta_path.replace("\\", "/").lower()
    if "/rf/" in norm_path or "rf_spectrum" in norm_path or meta.get("center_freq_hz") is not None:
        return MODALITY_RF
    if "/acoustic/" in norm_path or "acoustic_waveform" in norm_path or meta.get("audio_format") is not None:
        return MODALITY_ACOUSTIC
    if "/mock_fan/" in norm_path or "fan_rpm" in norm_path or meta.get("simulation_parameters") is not None:
        return MODALITY_FAN_SIMULATION
    return "UNKNOWN"


def validate_metadata_file(meta_path: str, base_dir: str, data_dir: str) -> EvidenceValidationRecord:
    """
    Validate a single metadata JSON file (legacy, new, or mixed) and its referenced raw data file.
    Does not mutate original metadata files on disk.
    """
    failures: List[str] = []
    warnings: List[str] = []
    inconsistencies: List[str] = []
    meta_dir = os.path.dirname(os.path.abspath(meta_path))

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        if not isinstance(meta, dict):
            raise ValueError("Metadata JSON root must be an object")
    except Exception as e:
        return EvidenceValidationRecord(
            capture_id="CORRUPTED",
            modality="UNKNOWN",
            plot_name=os.path.basename(meta_path),
            plot_path="",
            metadata_found=True,
            metadata_valid=False,
            metadata_path=os.path.abspath(meta_path),
            source_type="INVALID",
            source_mode="INVALID",
            sensor_id="UNKNOWN",
            acquisition_mode="UNKNOWN",
            capture_timestamp_iso="",
            sample_rate_hz=0.0,
            sample_count_recorded=0,
            raw_data_path="",
            raw_data_exists=False,
            raw_data_type="NONE",
            hash_verified=False,
            recorded_sha256="",
            computed_sha256="",
            samples_verified=False,
            actual_samples=0,
            timestamp_verified=False,
            validation_status="INVALID",
            hardware_provenance_note="INVALID: Corrupted JSON metadata.",
            failure_reasons=[f"Corrupted JSON file: {e}"],
            warnings=[],
            schema_compatibility="CORRUPTED",
            file_integrity_status="FAIL",
            source_classification="INVALID",
            hardware_provenance_assurance="UNTRUSTED",
            sample_rate_verification="INVALID_METADATA",
            sha256_verification_status="INVALID_METADATA",
            path_resolution_method="NOT_FOUND",
            metadata_inconsistencies=[],
        )

    modality = _infer_modality(meta, meta_path)

    # Track schema flavor without altering file on disk
    has_new_keys = any(k in meta for k in ("source_type", "timestamp", "data_file", "data_sha256"))
    has_legacy_keys = any(k in meta for k in ("source_mode", "capture_timestamp_iso", "raw_data_path", "raw_data_sha256"))
    if has_new_keys and has_legacy_keys:
        schema_compat = "MIXED_COMPATIBLE"
    elif has_new_keys:
        schema_compat = "NEW_SCHEMA"
    elif has_legacy_keys:
        schema_compat = "LEGACY_SCHEMA"
    else:
        schema_compat = "MINIMAL_OR_INCOMPLETE"

    # 1. Source classification resolution (new source_type vs legacy source_mode + data_source)
    has_st = _is_present(meta, "source_type")
    has_sm = _is_present(meta, "source_mode")
    has_ds = _is_present(meta, "data_source")

    norm_st = normalize_source_type(meta["source_type"]) if has_st else None
    norm_sm = normalize_source_type(meta["source_mode"]) if has_sm else None
    norm_ds = normalize_source_type(meta["data_source"]) if has_ds else None

    source_type = "UNKNOWN"
    source_mode = "UNKNOWN"

    if has_st and norm_st is None:
        failures.append(f"Unrecognized source_type value: {meta.get('source_type')!r}")
    if has_sm and norm_sm is None:
        failures.append(f"Unrecognized legacy source_mode value: {meta.get('source_mode')!r}")
    if has_ds and norm_ds is None:
        failures.append(f"Unrecognized data_source value: {meta.get('data_source')!r}")

    if has_st and has_sm:
        if norm_st is not None and norm_sm is not None and norm_st != norm_sm:
            msg = f"Conflicting source fields: source_type={meta.get('source_type')!r} vs source_mode={meta.get('source_mode')!r}"
            inconsistencies.append(msg)
            failures.append(msg)
            source_type = "INVALID"
            source_mode = "INVALID"
        elif norm_st is not None:
            source_type = norm_st
            source_mode = SOURCE_LABEL_MAP[norm_st]
        else:
            source_type = "INVALID"
            source_mode = "INVALID"
    elif has_st:
        source_type = norm_st if norm_st is not None else "INVALID"
        source_mode = SOURCE_LABEL_MAP[norm_st] if norm_st is not None else "INVALID"
    elif has_sm:
        source_type = norm_sm if norm_sm is not None else "INVALID"
        source_mode = SOURCE_LABEL_MAP[norm_sm] if norm_sm is not None else "INVALID"
    else:
        failures.append("Missing required source classification ('source_type' or 'source_mode')")
        source_type = "UNKNOWN"
        source_mode = "UNKNOWN"

    if has_ds and source_type in SOURCE_LABEL_MAP and norm_ds != source_type:
        msg = f"Conflicting data_source={meta.get('data_source')!r} for source_type={source_type!r}"
        inconsistencies.append(msg)
        failures.append(msg)
        source_type = "INVALID"
        source_mode = "INVALID"

    # Strict hardware vs simulation guardrails (never allow synthetic/simulated RPM as LIVE_HARDWARE)
    sensor_id = str(meta.get("sensor_id") or "").strip()
    if not sensor_id:
        failures.append("Missing required metadata field: 'sensor_id'")
        sensor_id = "UNKNOWN"

    acq_mode = str(meta.get("acquisition_mode") or "").strip() or "LEGACY_UNSPECIFIED"
    sensor_upper = sensor_id.upper()
    acq_upper = acq_mode.upper()

    if source_type == SOURCE_TYPE_LIVE_HARDWARE:
        if any(tok in sensor_upper for tok in ("SYNTHETIC", "VIRTUAL", "SIMULATOR", "SIM-", "MOCK")):
            msg = f"Source conflict: LIVE_HARDWARE conflicts with simulated/virtual sensor_id '{sensor_id}'"
            inconsistencies.append(msg)
            failures.append(msg)
            source_type = "INVALID"
            source_mode = "INVALID"
        elif any(tok in acq_upper for tok in ("SYNTHETIC", "SIMULATION", "SOFTWARE MODEL", "VIRTUAL")):
            msg = f"Source conflict: LIVE_HARDWARE conflicts with acquisition_mode '{acq_mode}'"
            inconsistencies.append(msg)
            failures.append(msg)
            source_type = "INVALID"
            source_mode = "INVALID"
        elif meta.get("is_synthetic") is True:
            msg = "Source conflict: LIVE_HARDWARE conflicts with is_synthetic=true"
            inconsistencies.append(msg)
            failures.append(msg)
            source_type = "INVALID"
            source_mode = "INVALID"

    # Simulated fan RPM may never be classified as tachometer hardware measurements
    rpm_source_upper = str(meta.get("rpm_source") or "").strip().upper()
    if modality == MODALITY_FAN_SIMULATION or rpm_source_upper == "SIMULATED":
        if source_type == SOURCE_TYPE_LIVE_HARDWARE and not meta.get("tachometer_attached", False):
            msg = "Simulated fan RPM cannot be classified as LIVE_HARDWARE without a physical tachometer"
            inconsistencies.append(msg)
            failures.append(msg)
            source_type = "INVALID"
            source_mode = "INVALID"

    # 2. Timestamp resolution & validation (ISO + Epoch, legacy vs new, tz-aware, no current-time substitution)
    has_iso_new = _is_present(meta, "timestamp")
    has_iso_old = _is_present(meta, "capture_timestamp_iso")
    has_ep_new = meta.get("timestamp_epoch") is not None
    has_ep_old = meta.get("capture_timestamp_epoch") is not None

    iso_dt_new, aware_new, err_iso_new = _parse_iso_timestamp(meta["timestamp"]) if has_iso_new else (None, False, None)
    iso_dt_old, aware_old, err_iso_old = _parse_iso_timestamp(meta["capture_timestamp_iso"]) if has_iso_old else (None, False, None)

    if err_iso_new:
        failures.append(f"Invalid 'timestamp': {err_iso_new}")
    if err_iso_old:
        failures.append(f"Invalid 'capture_timestamp_iso': {err_iso_old}")

    chosen_iso_str = ""
    chosen_iso_dt: Optional[datetime] = None
    chosen_iso_aware = False

    if has_iso_new and has_iso_old:
        chosen_iso_str = str(meta["timestamp"])
        if iso_dt_new is not None and iso_dt_old is not None:
            if aware_new and aware_old:
                if abs(iso_dt_new.timestamp() - iso_dt_old.timestamp()) > 2.0:
                    msg = f"Conflicting timestamps: timestamp='{meta['timestamp']}' vs capture_timestamp_iso='{meta['capture_timestamp_iso']}'"
                    inconsistencies.append(msg)
                    failures.append(msg)
            elif iso_dt_new.replace(tzinfo=None) != iso_dt_old.replace(tzinfo=None) or aware_new != aware_old:
                msg = f"Conflicting timestamps: timestamp='{meta['timestamp']}' vs capture_timestamp_iso='{meta['capture_timestamp_iso']}'"
                inconsistencies.append(msg)
                failures.append(msg)
            chosen_iso_dt = iso_dt_new
            chosen_iso_aware = aware_new
        elif bool(iso_dt_new) != bool(iso_dt_old):
            inconsistencies.append("Conflicting ISO timestamp validity between 'timestamp' and 'capture_timestamp_iso'")
    elif has_iso_new:
        chosen_iso_str = str(meta["timestamp"])
        chosen_iso_dt = iso_dt_new
        chosen_iso_aware = aware_new
    elif has_iso_old:
        chosen_iso_str = str(meta["capture_timestamp_iso"])
        chosen_iso_dt = iso_dt_old
        chosen_iso_aware = aware_old

    ep_new_val, err_ep_new = _parse_epoch_timestamp(meta["timestamp_epoch"], "timestamp_epoch") if has_ep_new else (None, None)
    ep_old_val, err_ep_old = _parse_epoch_timestamp(meta["capture_timestamp_epoch"], "capture_timestamp_epoch") if has_ep_old else (None, None)

    if err_ep_new:
        failures.append(err_ep_new)
    if err_ep_old:
        failures.append(err_ep_old)

    chosen_epoch: Optional[float] = None
    if has_ep_new and has_ep_old:
        if ep_new_val is not None and ep_old_val is not None:
            if abs(ep_new_val - ep_old_val) > 2.0:
                msg = f"Conflicting epoch timestamps: timestamp_epoch={ep_new_val} vs capture_timestamp_epoch={ep_old_val}"
                inconsistencies.append(msg)
                failures.append(msg)
            chosen_epoch = ep_new_val
    elif has_ep_new:
        chosen_epoch = ep_new_val
    elif has_ep_old:
        chosen_epoch = ep_old_val

    if chosen_iso_dt is not None and chosen_epoch is not None and chosen_iso_aware:
        if abs(chosen_iso_dt.timestamp() - chosen_epoch) > 5.0:
            msg = f"Timestamp conflict between ISO '{chosen_iso_str}' and epoch {chosen_epoch}"
            inconsistencies.append(msg)
            failures.append(msg)

    if not has_iso_new and not has_iso_old and not has_ep_new and not has_ep_old:
        failures.append("Missing required timestamp field ('timestamp' / 'capture_timestamp_iso')")
        timestamp_verified = False
    elif not has_iso_new and not has_iso_old:
        # Epoch-only metadata allowed if epoch is valid, though warn if ISO missing? Accept valid epoch cleanly
        timestamp_verified = (chosen_epoch is not None and not err_ep_new and not err_ep_old)
    else:
        timestamp_verified = (
            chosen_iso_dt is not None
            and not err_iso_new
            and not err_iso_old
            and not err_ep_new
            and not err_ep_old
            and not any("timestamp" in inc.lower() for inc in inconsistencies)
        )

    # 3. Sample rate resolution (sample_rate vs sample_rate_hz)
    has_sr_new = meta.get("sample_rate") is not None
    has_sr_old = meta.get("sample_rate_hz") is not None
    sr_new_val: Optional[float] = None
    sr_old_val: Optional[float] = None
    sr_hz = 0.0

    def _parse_rate(v: Any, name: str) -> Optional[float]:
        if isinstance(v, bool):
            failures.append(f"'{name}' must be numeric, not boolean")
            return None
        try:
            f = float(v)
            if not math.isfinite(f) or f <= 0:
                failures.append(f"'{name}' must be > 0 (got {v!r})")
                return None
            return f
        except (TypeError, ValueError):
            failures.append(f"'{name}' must be numeric (got {v!r})")
            return None

    if has_sr_new:
        sr_new_val = _parse_rate(meta["sample_rate"], "sample_rate")
    if has_sr_old:
        sr_old_val = _parse_rate(meta["sample_rate_hz"], "sample_rate_hz")

    if has_sr_new and has_sr_old:
        if sr_new_val is not None and sr_old_val is not None:
            if abs(sr_new_val - sr_old_val) > 1e-6:
                msg = f"Conflicting sample rate fields: sample_rate={sr_new_val} vs sample_rate_hz={sr_old_val}"
                inconsistencies.append(msg)
                failures.append(msg)
            sr_hz = sr_new_val
    elif has_sr_new and sr_new_val is not None:
        sr_hz = sr_new_val
    elif has_sr_old and sr_old_val is not None:
        sr_hz = sr_old_val
    elif not has_sr_new and not has_sr_old:
        failures.append("Missing required sample rate ('sample_rate' or 'sample_rate_hz')")

    # 4. Sample count resolution (sample_count vs num_frames)
    has_sc = meta.get("sample_count") is not None
    has_nf = meta.get("num_frames") is not None
    rec_samples = 0

    def _parse_count(v: Any, name: str) -> Optional[int]:
        if isinstance(v, bool):
            failures.append(f"'{name}' must be an integer, not boolean")
            return None
        try:
            iv = int(v)
            if iv <= 0:
                failures.append(f"'{name}' must be > 0 (got {v!r})")
                return None
            return iv
        except (TypeError, ValueError):
            failures.append(f"'{name}' must be an integer (got {v!r})")
            return None

    sc_val = _parse_count(meta["sample_count"], "sample_count") if has_sc else None
    nf_val = _parse_count(meta["num_frames"], "num_frames") if has_nf else None
    if has_sc and has_nf and sc_val is not None and nf_val is not None and sc_val != nf_val:
        msg = f"Conflicting sample counts: sample_count={sc_val} vs num_frames={nf_val}"
        inconsistencies.append(msg)
        failures.append(msg)
    if sc_val is not None:
        rec_samples = sc_val
    elif nf_val is not None:
        rec_samples = nf_val
    elif not has_sc and not has_nf:
        failures.append("Missing required sample count ('sample_count')")

    # 5. Raw data file path resolution (data_file vs raw_data_path)
    has_df_new = _is_present(meta, "data_file")
    has_df_old = _is_present(meta, "raw_data_path")
    raw_path_cfg = ""

    if has_df_new and has_df_old:
        raw_path_cfg = str(meta["data_file"]).strip()
        if _paths_conflict(str(meta["data_file"]), str(meta["raw_data_path"]), base_dir, data_dir, meta_dir):
            msg = f"Conflicting data file fields: data_file={meta['data_file']!r} vs raw_data_path={meta['raw_data_path']!r}"
            inconsistencies.append(msg)
            failures.append(msg)
    elif has_df_new:
        raw_path_cfg = str(meta["data_file"]).strip()
    elif has_df_old:
        raw_path_cfg = str(meta["raw_data_path"]).strip()
    else:
        failures.append("Missing required raw data path ('data_file' or 'raw_data_path')")

    raw_path, raw_exists, res_method = (
        resolve_evidence_path(raw_path_cfg, base_dir, data_dir, meta_dir=meta_dir)
        if raw_path_cfg
        else ("", False, "EMPTY")
    )

    if raw_path_cfg and not raw_exists:
        failures.append(f"Referenced raw data file is MISSING: {raw_path_cfg}")

    # Plot path resolution (plot_file vs plot_path, optional)
    has_pf_new = _is_present(meta, "plot_file")
    has_pf_old = _is_present(meta, "plot_path")
    plot_path_cfg = ""
    if has_pf_new and has_pf_old:
        plot_path_cfg = str(meta["plot_file"]).strip()
        if _paths_conflict(str(meta["plot_file"]), str(meta["plot_path"]), base_dir, data_dir, meta_dir):
            msg = f"Conflicting plot fields: plot_file={meta['plot_file']!r} vs plot_path={meta['plot_path']!r}"
            inconsistencies.append(msg)
            failures.append(msg)
    elif has_pf_new:
        plot_path_cfg = str(meta["plot_file"]).strip()
    elif has_pf_old:
        plot_path_cfg = str(meta["plot_path"]).strip()

    plot_path = ""
    if plot_path_cfg:
        plot_path, plot_exists, _ = resolve_evidence_path(plot_path_cfg, base_dir, data_dir, meta_dir=meta_dir)
        if not plot_exists:
            warnings.append(f"Plot image missing on disk: {plot_path_cfg}")

    plot_name = (
        os.path.basename(plot_path)
        if plot_path
        else (os.path.basename(plot_path_cfg) if plot_path_cfg else os.path.splitext(os.path.basename(meta_path))[0] + ".png")
    )

    # 6. SHA-256 resolution & format check (data_sha256 vs raw_data_sha256)
    has_sh_new = _is_present(meta, "data_sha256")
    has_sh_old = _is_present(meta, "raw_data_sha256")
    rec_hash = ""
    hash_format_valid = False

    if has_sh_new and has_sh_old:
        s_new = str(meta["data_sha256"]).strip().lower()
        s_old = str(meta["raw_data_sha256"]).strip().lower()
        rec_hash = s_new
        if s_new != s_old:
            msg = f"Conflicting SHA-256 fields: data_sha256={s_new[:12]}... vs raw_data_sha256={s_old[:12]}..."
            inconsistencies.append(msg)
            failures.append(msg)
    elif has_sh_new:
        rec_hash = str(meta["data_sha256"]).strip().lower()
    elif has_sh_old:
        rec_hash = str(meta["raw_data_sha256"]).strip().lower()

    if not rec_hash:
        sha_status = "MISSING_EXPECTED_HASH"
        failures.append("Missing expected SHA-256 digest ('data_sha256' or 'raw_data_sha256')")
    elif not _SHA256_HEX_RE.fullmatch(rec_hash):
        sha_status = "MALFORMED_EXPECTED_HASH"
        failures.append(f"Malformed expected SHA-256 digest (expected 64 hex characters, got {rec_hash!r})")
    else:
        hash_format_valid = True
        sha_status = "PENDING"

    # Optional field sanity checks (when present)
    if meta.get("fft_size") is not None:
        try:
            if int(meta["fft_size"]) < 64:
                failures.append(f"Invalid RF fft_size: {meta['fft_size']}")
        except (TypeError, ValueError):
            failures.append(f"RF fft_size must be an integer (got {meta['fft_size']!r})")

    if meta.get("channels") is not None:
        try:
            if int(meta["channels"]) not in (1, 2):
                failures.append(f"Invalid acoustic channels: {meta['channels']}")
        except (TypeError, ValueError):
            failures.append(f"Acoustic channels must be integer 1 or 2 (got {meta['channels']!r})")

    capture_id = str(meta.get("capture_id") or f"LEGACY-{os.path.splitext(os.path.basename(meta_path))[0]}")
    meta_valid = (len(failures) == 0)

    # 7. Actual Data Integrity Verification on disk
    computed_hash = ""
    hash_verified = False
    actual_samples = 0
    samples_verified = False
    raw_type = "NONE"
    sr_verification = "INVALID_METADATA" if sr_hz <= 0 else "UNAVAILABLE"

    if not raw_exists:
        if hash_format_valid:
            sha_status = "SKIPPED_MISSING_FILE"
        file_integrity_status = "MISSING"
    else:
        ext = os.path.splitext(raw_path)[1].lower()
        file_integrity_ok = True

        if ext == ".npy":
            raw_type = "NUMPY_ARRAY"
            try:
                arr = np.load(raw_path, allow_pickle=False)
                if arr.ndim == 0:
                    failures.append(f"Invalid 0-D scalar array in {os.path.basename(raw_path)}")
                    file_integrity_ok = False
                else:
                    actual_samples = int(arr.shape[0])
                    samples_verified = (rec_samples > 0 and actual_samples == rec_samples)
                    if not samples_verified:
                        failures.append(
                            f"Sample count MISMATCH for {os.path.basename(raw_path)}: metadata={rec_samples}, actual={actual_samples}"
                        )
                        file_integrity_ok = False

                    arr_hash = compute_array_sha256(arr)
                    file_hash = compute_file_sha256(raw_path)
                    if hash_format_valid:
                        if rec_hash == file_hash:
                            hash_verified = True
                            computed_hash = file_hash
                            sha_status = "MATCH"
                        elif rec_hash == arr_hash:
                            hash_verified = True
                            computed_hash = arr_hash
                            sha_status = "MATCH"
                        else:
                            computed_hash = arr_hash
                            sha_status = "MISMATCH"
                            failures.append(
                                f"SHA-256 MISMATCH for {os.path.basename(raw_path)}: expected={rec_hash[:12]}..., actual={arr_hash[:12]}..."
                            )
                            file_integrity_ok = False
                    else:
                        computed_hash = arr_hash
                        file_integrity_ok = False
            except Exception as e:
                failures.append(f"Failed to inspect .npy file: {e}")
                file_integrity_ok = False

        elif ext in (".wav", ".wave"):
            raw_type = "AUDIO_WAV"
            try:
                info = sf.info(raw_path)
                actual_samples = int(info.frames)
                samples_verified = (rec_samples > 0 and actual_samples == rec_samples)
                if not samples_verified:
                    failures.append(
                        f"Audio frame count MISMATCH for {os.path.basename(raw_path)}: metadata={rec_samples}, actual={actual_samples}"
                    )
                    file_integrity_ok = False

                if sr_hz > 0:
                    if int(info.samplerate) == int(round(sr_hz)):
                        sr_verification = "VERIFIED"
                    else:
                        sr_verification = "MISMATCH"
                        failures.append(f"Audio sample rate MISMATCH: metadata={sr_hz}, wav={info.samplerate}")
                        file_integrity_ok = False
                else:
                    sr_verification = "INVALID_METADATA"

                rec_channels = meta.get("channels")
                if rec_channels is not None and int(info.channels) != int(rec_channels):
                    failures.append(f"Audio channel count MISMATCH: metadata={rec_channels}, wav={info.channels}")
                    file_integrity_ok = False

                file_hash = compute_file_sha256(raw_path)
                computed_hash = file_hash
                if hash_format_valid:
                    if file_hash == rec_hash:
                        hash_verified = True
                        sha_status = "MATCH"
                    else:
                        sha_status = "MISMATCH"
                        failures.append(
                            f"WAV SHA-256 MISMATCH for {os.path.basename(raw_path)}: expected={rec_hash[:12]}..., actual={file_hash[:12]}..."
                        )
                        file_integrity_ok = False
                else:
                    file_integrity_ok = False
            except Exception as e:
                failures.append(f"Failed to inspect WAV file: {e}")
                file_integrity_ok = False

        elif ext == ".csv":
            raw_type = "TIMELINE_CSV"
            try:
                with open(raw_path, "r", encoding="utf-8", newline="") as f:
                    reader = csv.reader(f)
                    non_empty_rows = [row for row in reader if any(cell.strip() for cell in row)]
                if len(non_empty_rows) <= 1:
                    actual_samples = 0
                else:
                    actual_samples = len(non_empty_rows) - 1
                samples_verified = (rec_samples > 0 and actual_samples == rec_samples)
                if not samples_verified:
                    failures.append(
                        f"CSV row count MISMATCH for {os.path.basename(raw_path)}: metadata={rec_samples}, actual={actual_samples}"
                    )
                    file_integrity_ok = False

                file_hash = compute_file_sha256(raw_path)
                computed_hash = file_hash
                if hash_format_valid:
                    if file_hash == rec_hash:
                        hash_verified = True
                        sha_status = "MATCH"
                    else:
                        sha_status = "MISMATCH"
                        failures.append(
                            f"CSV SHA-256 MISMATCH for {os.path.basename(raw_path)}: expected={rec_hash[:12]}..., actual={file_hash[:12]}..."
                        )
                        file_integrity_ok = False
                else:
                    file_integrity_ok = False
            except Exception as e:
                failures.append(f"Failed to inspect CSV timeline: {e}")
                file_integrity_ok = False
        else:
            raw_type = "BINARY_FILE"
            try:
                file_hash = compute_file_sha256(raw_path)
                computed_hash = file_hash
                if hash_format_valid:
                    if file_hash == rec_hash:
                        hash_verified = True
                        sha_status = "MATCH"
                    else:
                        sha_status = "MISMATCH"
                        failures.append(f"SHA-256 MISMATCH for {os.path.basename(raw_path)}")
                        file_integrity_ok = False
                else:
                    file_integrity_ok = False
            except Exception as e:
                failures.append(f"Failed to read raw file: {e}")
                file_integrity_ok = False

        file_integrity_status = "PASS" if (file_integrity_ok and hash_verified and samples_verified) else "FAIL"

    if failures:
        status = "INVALID"
    elif warnings:
        status = "PARTIALLY VERIFIED"
    else:
        status = "VERIFIED"

    prov_note = _determine_hardware_provenance_note(
        source_type,
        status,
        inconsistent=bool(inconsistencies),
    )
    prov_assurance = _determine_provenance_assurance(source_type, status)

    return EvidenceValidationRecord(
        capture_id=capture_id,
        modality=modality,
        plot_name=plot_name,
        plot_path=plot_path,
        metadata_found=True,
        metadata_valid=meta_valid,
        metadata_path=os.path.abspath(meta_path),
        source_type=source_type,
        source_mode=source_mode,
        sensor_id=sensor_id,
        acquisition_mode=acq_mode,
        capture_timestamp_iso=chosen_iso_str,
        sample_rate_hz=sr_hz,
        sample_count_recorded=rec_samples,
        raw_data_path=raw_path,
        raw_data_exists=raw_exists,
        raw_data_type=raw_type,
        hash_verified=hash_verified,
        recorded_sha256=rec_hash,
        computed_sha256=computed_hash,
        samples_verified=samples_verified,
        actual_samples=actual_samples,
        timestamp_verified=timestamp_verified,
        validation_status=status,
        hardware_provenance_note=prov_note,
        failure_reasons=failures,
        warnings=warnings,
        schema_compatibility=schema_compat,
        file_integrity_status=file_integrity_status,
        source_classification=source_type,
        hardware_provenance_assurance=prov_assurance,
        sample_rate_verification=sr_verification,
        sha256_verification_status=sha_status,
        timestamp_epoch=chosen_epoch,
        path_resolution_method=res_method,
        metadata_inconsistencies=inconsistencies,
    )


def discover_metadata_files(base_dir: str, data_dir: Optional[str] = None) -> Tuple[List[str], List[str]]:
    """
    Discover metadata JSON files across both current ('aetherhound/data/...') and legacy ('data/...')
    directories without scanning unrelated folders or processing duplicates.
    Returns (sorted_unique_metadata_paths, search_data_roots).
    """
    resolved_base = os.path.abspath(base_dir)
    candidate_data_roots: List[str] = []

    if data_dir:
        resolved_data = os.path.abspath(data_dir)
        candidate_data_roots.append(resolved_data)
        nested_ah_data = os.path.join(resolved_data, "aetherhound", "data")
        if os.path.isdir(nested_ah_data):
            candidate_data_roots.append(nested_ah_data)
    else:
        for root_cand in (
            os.path.join(resolved_base, "data"),
            os.path.join(resolved_base, "aetherhound", "data"),
        ):
            candidate_data_roots.append(os.path.abspath(root_cand))

    # Deduplicate data roots by realpath
    unique_roots: List[str] = []
    seen_roots = set()
    for r in candidate_data_roots:
        rp = os.path.realpath(r)
        if rp not in seen_roots:
            seen_roots.add(rp)
            unique_roots.append(r)

    meta_files_by_real: Dict[str, str] = {}
    for droot in unique_roots:
        if not os.path.isdir(droot):
            continue
        for sub in ("rf/metadata/*.json", "acoustic/metadata/*.json", "mock_fan/metadata/*.json"):
            for match in glob.glob(os.path.join(droot, sub)):
                if os.path.isfile(match):
                    rp = os.path.realpath(match)
                    if rp not in meta_files_by_real:
                        meta_files_by_real[rp] = os.path.abspath(match)

    sorted_paths = sorted(meta_files_by_real.values())
    return sorted_paths, unique_roots


def _select_safe_report_targets(
    resolved_base: str,
    resolved_data: str,
    sync_public: bool,
    output_dir: Optional[str],
    output_path: Optional[str],
    test_mode: bool,
    overwrite: bool,
) -> Tuple[List[str], List[str]]:
    """
    Determine non-destructive JSON audit report output paths.
    Never overwrites existing production audit reports unless overwrite=True.
    Returns (write_targets, preserved_existing_targets).
    """
    if test_mode:
        tmp_dir = tempfile.mkdtemp(prefix="aetherhound_audit_")
        return [os.path.join(tmp_dir, "evidence_audit_report.json")], []

    if output_path:
        target = os.path.abspath(output_path)
        if os.path.exists(target) and not overwrite:
            tmp_dir = tempfile.mkdtemp(prefix="aetherhound_audit_")
            return [os.path.join(tmp_dir, os.path.basename(target))], [target]
        return [target], []

    if output_dir:
        out_dir_abs = os.path.abspath(output_dir)
        target = os.path.join(out_dir_abs, "evidence_audit_report.json")
        if os.path.exists(target) and not overwrite:
            tmp_dir = tempfile.mkdtemp(prefix="aetherhound_audit_")
            return [os.path.join(tmp_dir, "evidence_audit_report.json")], [target]
        return [target], []

    # Production candidate locations
    prod_targets = [os.path.join(resolved_data, "evidence_audit_report.json")]
    if sync_public:
        prod_targets.append(os.path.join(resolved_base, "public", "data", "evidence_audit_report.json"))
        prod_targets.append(os.path.join(resolved_base, "aetherhound", "data", "evidence_audit_report.json"))

    # Deduplicate by realpath preserving order
    unique_prod: List[str] = []
    seen = set()
    for p in prod_targets:
        rp = os.path.realpath(p)
        if rp not in seen:
            seen.add(rp)
            unique_prod.append(os.path.abspath(p))

    existing_prod = [p for p in unique_prod if os.path.exists(p)]
    if existing_prod and not overwrite:
        # Preserve existing production audit reports; write this run cleanly to a temp location
        tmp_dir = tempfile.mkdtemp(prefix="aetherhound_audit_")
        return [os.path.join(tmp_dir, "evidence_audit_report.json")], existing_prod

    return unique_prod, []


def run_full_audit(
    base_dir: str,
    data_dir: Optional[str] = None,
    write_report: bool = True,
    sync_public: bool = True,
    output_dir: Optional[str] = None,
    output_path: Optional[str] = None,
    test_mode: bool = False,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """
    Execute complete Day 1 + Day 2 backward-compatible provenance audit across legacy and current
    metadata directories, with non-destructive report output handling.
    """
    resolved_base = os.path.abspath(base_dir)
    resolved_data = os.path.abspath(data_dir) if data_dir else os.path.join(resolved_base, "data")

    meta_files, search_roots = discover_metadata_files(resolved_base, data_dir=data_dir)
    records: List[EvidenceValidationRecord] = []
    referenced_plots = set()
    processed_meta_real = set()

    for mpath in meta_files:
        processed_meta_real.add(os.path.realpath(mpath))
        rec = validate_metadata_file(mpath, resolved_base, resolved_data)
        records.append(rec)
        if rec.plot_path and os.path.exists(rec.plot_path):
            referenced_plots.add(os.path.realpath(rec.plot_path))

    # Check for orphaned PNG plots not backed by verified metadata
    plot_files_map: Dict[str, str] = {}
    for droot in search_roots:
        plots_root = os.path.join(droot, "plots")
        if not os.path.isdir(plots_root):
            continue
        for p in glob.glob(os.path.join(plots_root, "**", "*.png"), recursive=True):
            if os.path.isfile(p):
                rp = os.path.realpath(p)
                if rp not in plot_files_map:
                    plot_files_map[rp] = os.path.abspath(p)

    for rp_plot, pfile in sorted(plot_files_map.items(), key=lambda kv: kv[1]):
        if rp_plot not in referenced_plots:
            adj_json = os.path.splitext(pfile)[0] + ".json"
            if os.path.isfile(adj_json):
                adj_real = os.path.realpath(adj_json)
                if adj_real not in processed_meta_real:
                    processed_meta_real.add(adj_real)
                    rec = validate_metadata_file(adj_json, resolved_base, resolved_data)
                    records.append(rec)
            else:
                records.append(
                    EvidenceValidationRecord(
                        capture_id="ORPHANED",
                        modality="ORPHAN_PLOT",
                        plot_name=os.path.basename(pfile),
                        plot_path=pfile,
                        metadata_found=False,
                        metadata_valid=False,
                        metadata_path=None,
                        source_type="INVALID",
                        source_mode="INVALID",
                        sensor_id="UNTRACED",
                        acquisition_mode="UNKNOWN",
                        capture_timestamp_iso="",
                        sample_rate_hz=0.0,
                        sample_count_recorded=0,
                        raw_data_path="",
                        raw_data_exists=False,
                        raw_data_type="NONE",
                        hash_verified=False,
                        recorded_sha256="",
                        computed_sha256="",
                        samples_verified=False,
                        actual_samples=0,
                        timestamp_verified=False,
                        validation_status="INVALID",
                        hardware_provenance_note="INVALID: Orphaned plot image without provenance metadata.",
                        failure_reasons=[f"Missing provenance metadata JSON for plot: {os.path.basename(pfile)}"],
                        warnings=[],
                        schema_compatibility="NONE",
                        file_integrity_status="MISSING",
                        source_classification="INVALID",
                        hardware_provenance_assurance="UNTRUSTED",
                        sample_rate_verification="UNAVAILABLE",
                        sha256_verification_status="MISSING_EXPECTED_HASH",
                        path_resolution_method="NOT_FOUND",
                        metadata_inconsistencies=[],
                    )
                )

    verified_count = sum(1 for r in records if r.validation_status == "VERIFIED")
    partial_count = sum(1 for r in records if r.validation_status == "PARTIALLY VERIFIED")
    invalid_count = sum(1 for r in records if r.validation_status == "INVALID")

    hardware_count = sum(1 for r in records if r.source_type == SOURCE_TYPE_LIVE_HARDWARE and r.validation_status != "INVALID")
    sim_count = sum(1 for r in records if r.source_type == SOURCE_TYPE_SYNTHETIC_SIMULATION and r.validation_status != "INVALID")
    recorded_count = sum(1 for r in records if r.source_type == SOURCE_TYPE_RECORDED_HARDWARE and r.validation_status != "INVALID")

    if len(records) == 0 or invalid_count > 0:
        overall_result = "INVALID"
    elif partial_count > 0:
        overall_result = "PARTIALLY VERIFIED"
    else:
        overall_result = "VERIFIED"

    # Build backward-compatible + Day 2 plot serialization
    serialized_records = []
    for r in records:
        d = asdict(r)
        if r.validation_status == "INVALID":
            d["audit_status"] = "FAIL_INTEGRITY"
        elif r.source_type == SOURCE_TYPE_LIVE_HARDWARE:
            d["audit_status"] = "PASS_HARDWARE"
        elif r.source_type == SOURCE_TYPE_SYNTHETIC_SIMULATION:
            d["audit_status"] = "PASS_SIMULATION"
        else:
            d["audit_status"] = "PASS_RECORDED"
        serialized_records.append(d)

    written_paths: List[str] = []
    preserved_paths: List[str] = []

    summary: Dict[str, Any] = {
        "audit_timestamp_iso": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "audit_timestamp_epoch": time.time(),
        "overall_result": overall_result,
        "audit_passed": (overall_result in ("VERIFIED", "PARTIALLY VERIFIED") and invalid_count == 0 and len(records) > 0),
        "total_records_audited": len(records),
        "total_plots_audited": len(records),
        "total_passed": verified_count + partial_count,
        "verified_count": verified_count,
        "partially_verified_count": partial_count,
        "failed_or_orphaned_count": invalid_count,
        "hardware_derived_count": hardware_count,
        "synthetic_simulation_count": sim_count,
        "recorded_hardware_count": recorded_count,
        "integrity_summary": {
            "file_integrity_passed_count": sum(1 for r in records if r.file_integrity_status == "PASS"),
            "file_integrity_failed_count": sum(1 for r in records if r.file_integrity_status != "PASS"),
            "metadata_inconsistency_count": sum(len(r.metadata_inconsistencies) for r in records),
            "missing_raw_files_count": sum(1 for r in records if not r.raw_data_exists),
            "hash_mismatch_count": sum(1 for r in records if r.sha256_verification_status == "MISMATCH"),
        },
        "provenance_disclaimer": (
            "File-integrity validation confirms metadata schemas, sample counts, and SHA-256 digests on disk. "
            "Hardware provenance indicates whether capture runtime attested physical devices vs simulation; "
            "disk metadata alone cannot independently prove physical hardware origin without cryptographic device signing."
        ),
        "report_output_path": None,
        "report_output_paths": [],
        "preserved_existing_reports": [],
        "plots": serialized_records,
    }

    if write_report:
        out_targets, preserved_paths = _select_safe_report_targets(
            resolved_base=resolved_base,
            resolved_data=resolved_data,
            sync_public=sync_public,
            output_dir=output_dir,
            output_path=output_path,
            test_mode=test_mode,
            overwrite=overwrite,
        )
        summary["preserved_existing_reports"] = preserved_paths
        for outp in out_targets:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(outp)), exist_ok=True)
                written_paths.append(outp)
            except Exception as e:
                print(f"[!] Warning: Could not prepare audit output directory for {outp}: {e}")

        summary["report_output_paths"] = written_paths
        summary["report_output_path"] = written_paths[0] if written_paths else None

        for outp in written_paths:
            try:
                with open(outp, "w", encoding="utf-8") as f:
                    json.dump(summary, f, indent=2)
            except Exception as e:
                print(f"[!] Warning: Could not write audit report to {outp}: {e}")

    return summary


def print_audit_report(summary: Dict[str, Any]) -> None:
    """Print Day 1/Day 2 evidence validation summary separating file integrity from hardware provenance."""
    print("\nAETHERHOUND EVIDENCE VALIDATION")
    print("=" * 68)

    plots = summary.get("plots", [])
    rf_recs = [p for p in plots if p["modality"] == MODALITY_RF]
    ac_recs = [p for p in plots if p["modality"] == MODALITY_ACOUSTIC]
    fan_recs = [p for p in plots if p["modality"] == MODALITY_FAN_SIMULATION]
    other_recs = [p for p in plots if p["modality"] not in (MODALITY_RF, MODALITY_ACOUSTIC, MODALITY_FAN_SIMULATION)]

    def _print_group(title: str, recs: List[Dict[str, Any]], empty_msg: str) -> None:
        print(f"\n{title}:")
        if not recs:
            print(f"  {empty_msg}")
        for r in recs:
            raw_label = os.path.basename(r["raw_data_path"]) if r["raw_data_path"] else "MISSING"
            print(f"  Capture ID:       {r['capture_id']}")
            print(f"  Schema Compat:    {r.get('schema_compatibility', 'UNKNOWN')}")
            print(f"  Source Class:     {r.get('source_classification', r['source_type'])} ({r['source_mode']})")
            print(f"  Metadata Valid:   {'VALID' if r['metadata_valid'] else 'INVALID'}")
            print(f"  File Integrity:   {r.get('file_integrity_status', 'UNKNOWN')} ({raw_label})")
            print(f"  Sample Count:     {'VERIFIED' if r['samples_verified'] else 'MISMATCH'} ({r['actual_samples']} / {r['sample_count_recorded']})")
            print(f"  Sample Rate:      {r.get('sample_rate_verification', 'UNAVAILABLE')} ({r['sample_rate_hz']} Hz)")
            print(f"  SHA-256 Status:   {r.get('sha256_verification_status', 'MATCH' if r['hash_verified'] else 'FAIL')}")
            print(f"  Record Status:    {r['validation_status']}")
            print(f"  Provenance Note:  {r['hardware_provenance_note']}")
            for inc in r.get("metadata_inconsistencies", []):
                print(f"    [!] INCONSISTENCY: {inc}")
            for err in r["failure_reasons"]:
                if err not in r.get("metadata_inconsistencies", []):
                    print(f"    [!] ERROR: {err}")

    _print_group("RF EVIDENCE", rf_recs, "Metadata: MISSING (No RF capture metadata found)")
    _print_group("ACOUSTIC EVIDENCE", ac_recs, "Metadata: MISSING (No acoustic capture metadata found)")
    _print_group("FAN SIMULATION", fan_recs, "RPM Metadata: MISSING")
    if other_recs:
        _print_group("OTHER / ORPHANED ARTIFACTS", other_recs, "")

    print("\nOVERALL RESULT:")
    print(f"  {summary['overall_result']}")
    print(
        f"  (Verified: {summary['verified_count']} | Partial: {summary['partially_verified_count']} | Invalid: {summary['failed_or_orphaned_count']})"
    )
    print(
        f"  Hardware-Attributed: {summary['hardware_derived_count']} | Recorded Hardware: {summary['recorded_hardware_count']} | Synthetic Simulation: {summary['synthetic_simulation_count']}"
    )

    preserved = summary.get("preserved_existing_reports") or []
    if preserved:
        print(f"  [SAFE MODE] Existing audit report(s) preserved unchanged: {', '.join(preserved)}")
        print("              (Pass --overwrite to update existing production reports.)")
    if summary.get("report_output_path"):
        print(f"  Report Output:    {summary['report_output_path']}")
    print("=" * 68 + "\n")

    if RICH_AVAILABLE and plots:
        console = Console()
        table = Table(title="AetherHound Evidence Provenance Table", show_header=True, header_style="bold cyan")
        table.add_column("Capture ID", style="dim")
        table.add_column("Modality")
        table.add_column("Source Class")
        table.add_column("Schema")
        table.add_column("Raw File")
        table.add_column("Samples", justify="right")
        table.add_column("Integrity")
        table.add_column("Status")

        for p in plots:
            st = p["validation_status"]
            st_fmt = f"[bold green]{st}[/bold green]" if st == "VERIFIED" else (
                f"[bold yellow]{st}[/bold yellow]" if st == "PARTIALLY VERIFIED" else f"[bold red]{st}[/bold red]"
            )
            integ = p.get("file_integrity_status", "FAIL")
            integ_fmt = "[green]PASS[/green]" if integ == "PASS" else f"[red]{integ}[/red]"
            table.add_row(
                p["capture_id"],
                p["modality"],
                p.get("source_classification", p["source_type"]),
                p.get("schema_compatibility", "-"),
                os.path.basename(p["raw_data_path"]) if p["raw_data_path"] else "MISSING",
                f"{p['actual_samples']:,}",
                integ_fmt,
                st_fmt,
            )
        console.print(table)
        console.print()


def main():
    parser = argparse.ArgumentParser(description="AetherHound Day 2 Backward-Compatible Evidence Validation Utility")
    parser.add_argument("--base-dir", default=".", help="Base workspace directory")
    parser.add_argument("--data-dir", default=None, help="Explicit data directory to validate")
    parser.add_argument("--output-dir", default=None, help="Separate output directory for evidence_audit_report.json")
    parser.add_argument("--output-path", "--output", dest="output_path", default=None, help="Explicit output JSON report path")
    parser.add_argument("--test-mode", action="store_true", help="Non-destructive test mode (writes report to a temporary directory)")
    parser.add_argument("--overwrite", action="store_true", help="Explicitly overwrite existing production audit report(s)")
    parser.add_argument("--no-public-sync", action="store_true", help="Do not mirror report to public/data")
    parser.add_argument("--json", action="store_true", help="Print JSON summary only")
    args = parser.parse_args()

    summary = run_full_audit(
        base_dir=args.base_dir,
        data_dir=args.data_dir,
        write_report=True,
        sync_public=not args.no_public_sync,
        output_dir=args.output_dir,
        output_path=args.output_path,
        test_mode=args.test_mode,
        overwrite=args.overwrite,
    )

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print_audit_report(summary)

    if summary["overall_result"] == "INVALID":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
