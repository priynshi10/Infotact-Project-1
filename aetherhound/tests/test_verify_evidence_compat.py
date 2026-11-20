"""
Comprehensive Day 2 Tests for Backward-Compatible Evidence Verification & Integrity Validation.
Covers legacy metadata, new metadata, compatibility conflicts, cross-platform path resolution,
file integrity validation (SHA-256, sample count, sample rate, missing files), strict source
classification, metadata discovery across legacy + current paths, and non-destructive report output.

All tests execute completely offline without physical RTL-SDR or microphone hardware.
"""

import json
import os
import subprocess
import sys
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

from aetherhound.core.evidence_metadata import (
    compute_array_sha256,
    compute_file_sha256,
    save_metadata,
)
from aetherhound.scripts.verify_evidence import (
    PlotAuditResult,
    discover_metadata_files,
    resolve_evidence_path,
    run_full_audit,
    validate_metadata_file,
)


def _create_sample_wav(path, frames: int = 22050, sr: int = 44100, channels: int = 1) -> str:
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    data = np.zeros((frames, channels), dtype=np.float32) if channels > 1 else np.zeros(frames, dtype=np.float32)
    sf.write(str(path), data, sr)
    return compute_file_sha256(str(path))


def _create_sample_npy(path, length: int = 4096) -> str:
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    arr = (np.arange(length, dtype=np.float32) * 0.001 + 1j * 0.002).astype(np.complex64)
    np.save(str(path), arr)
    return compute_array_sha256(arr)


def _create_sample_csv(path, rows: int = 50) -> str:
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    lines = ["time_sec,rpm,state"]
    for i in range(rows):
        lines.append(f"{i * 0.02:.2f},1200.0,0")
    with open(str(path), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return compute_file_sha256(str(path))


# ---------------------------------------------------------------------------
# 1. LEGACY & NEW METADATA SUPPORT
# ---------------------------------------------------------------------------

def test_valid_legacy_metadata_verification(tmp_path):
    raw_wav = tmp_path / "data" / "acoustic" / "raw" / "legacy_capture.wav"
    sha = _create_sample_wav(raw_wav, frames=44100, sr=44100)

    legacy_meta = {
        "modality": "ACOUSTIC",
        "source_mode": "LIVE HARDWARE",
        "sensor_id": "MIC-01",
        "capture_timestamp_iso": "2026-11-12T10:00:00Z",
        "capture_timestamp_epoch": 1794477600.0,
        "sample_rate_hz": 44100,
        "sample_count": 44100,
        "raw_data_path": "data/acoustic/raw/legacy_capture.wav",
        "raw_data_sha256": sha,
    }
    meta_path = tmp_path / "data" / "acoustic" / "metadata" / "legacy_capture.json"
    save_metadata(legacy_meta, str(meta_path))

    report = run_full_audit(str(tmp_path), write_report=False)
    assert report["overall_result"] == "VERIFIED"
    assert report["hardware_derived_count"] == 1
    rec = report["plots"][0]
    assert isinstance(PlotAuditResult(**{k: v for k, v in rec.items() if k != "audit_status"}), PlotAuditResult)
    assert rec["schema_compatibility"] == "LEGACY_SCHEMA"
    assert rec["source_type"] == "LIVE_HARDWARE"
    assert rec["source_mode"] == "LIVE HARDWARE"
    assert rec["capture_timestamp_iso"] == "2026-11-12T10:00:00Z"
    assert rec["hash_verified"] is True
    assert rec["samples_verified"] is True
    assert rec["sample_rate_verification"] == "VERIFIED"
    assert rec["timestamp_verified"] is True
    assert rec["validation_status"] == "VERIFIED"


def test_valid_new_metadata_verification(tmp_path):
    raw_npy = tmp_path / "aetherhound" / "data" / "rf" / "raw" / "new_rf.npy"
    sha = _create_sample_npy(raw_npy, length=8192)

    new_meta = {
        "capture_id": "RF-NEW-001",
        "modality": "RF",
        "source_type": "RECORDED_HARDWARE",
        "sensor_id": "SDR-01",
        "timestamp": "2026-11-13T12:30:00+02:00",
        "timestamp_epoch": 1794565800.0,
        "sample_rate": 2048000,
        "sample_count": 8192,
        "data_file": "aetherhound/data/rf/raw/new_rf.npy",
        "data_sha256": sha,
        "center_freq_hz": 433920000.0,
    }
    meta_path = tmp_path / "aetherhound" / "data" / "rf" / "metadata" / "new_rf.json"
    save_metadata(new_meta, str(meta_path))

    report = run_full_audit(str(tmp_path), write_report=False)
    assert report["overall_result"] == "VERIFIED"
    assert report["recorded_hardware_count"] == 1
    assert report["hardware_derived_count"] == 0
    rec = report["plots"][0]
    assert rec["schema_compatibility"] == "NEW_SCHEMA"
    assert rec["source_type"] == "RECORDED_HARDWARE"
    assert "NOT LIVE ACQUISITION" in rec["hardware_provenance_note"]
    assert rec["sample_rate_verification"] == "UNAVAILABLE"
    assert rec["timestamp_verified"] is True


# ---------------------------------------------------------------------------
# 2. COMPATIBILITY: MIXED, OPTIONAL, MISSING REQUIRED, CONFLICTS
# ---------------------------------------------------------------------------

def test_mixed_old_and_new_fields_consistent_prefers_new(tmp_path):
    raw_csv = tmp_path / "data" / "mock_fan" / "rpm" / "fan.csv"
    sha = _create_sample_csv(raw_csv, rows=25)

    mixed_meta = {
        "modality": "FAN_SIMULATION",
        "source_type": "SYNTHETIC_SIMULATION",
        "source_mode": "SYNTHETIC SIMULATION",
        "sensor_id": "FAN-SIM-01",
        "timestamp": "2026-11-13T18:00:00Z",
        "capture_timestamp_iso": "2026-11-13T18:00:00+00:00",
        "timestamp_epoch": 1794592800.0,
        "capture_timestamp_epoch": 1794592800.0,
        "sample_rate": 50.0,
        "sample_rate_hz": 50.0,
        "sample_count": 25,
        "data_file": "data/mock_fan/rpm/fan.csv",
        "raw_data_path": "data/mock_fan/rpm/fan.csv",
        "data_sha256": sha,
        "raw_data_sha256": sha,
        "rpm_source": "SIMULATED",
    }
    meta_path = tmp_path / "data" / "mock_fan" / "metadata" / "fan.json"
    save_metadata(mixed_meta, str(meta_path))

    rec = validate_metadata_file(str(meta_path), str(tmp_path), str(tmp_path / "data"))
    assert rec.schema_compatibility == "MIXED_COMPATIBLE"
    assert rec.validation_status == "VERIFIED"
    assert rec.capture_timestamp_iso == "2026-11-13T18:00:00Z"
    assert rec.metadata_inconsistencies == []


@pytest.mark.parametrize(
    "missing_field",
    ["source", "timestamp", "sample_rate", "sample_count", "data_file", "sha256", "sensor_id"],
)
def test_missing_required_fields_rejected(tmp_path, missing_field):
    raw_wav = tmp_path / "data" / "acoustic" / "raw" / "req.wav"
    sha = _create_sample_wav(raw_wav, frames=11025, sr=44100)

    meta = {
        "modality": "ACOUSTIC",
        "source_type": "SYNTHETIC_SIMULATION",
        "sensor_id": "MIC-01 (VIRTUAL)",
        "timestamp": "2026-11-13T18:00:00Z",
        "sample_rate": 44100,
        "sample_count": 11025,
        "data_file": "data/acoustic/raw/req.wav",
        "data_sha256": sha,
    }
    key_map = {
        "source": "source_type",
        "timestamp": "timestamp",
        "sample_rate": "sample_rate",
        "sample_count": "sample_count",
        "data_file": "data_file",
        "sha256": "data_sha256",
        "sensor_id": "sensor_id",
    }
    del meta[key_map[missing_field]]

    meta_path = tmp_path / "data" / "acoustic" / "metadata" / "req.json"
    save_metadata(meta, str(meta_path))

    rec = validate_metadata_file(str(meta_path), str(tmp_path), str(tmp_path / "data"))
    assert rec.validation_status == "INVALID"
    assert len(rec.failure_reasons) >= 1


def test_conflicting_old_and_new_fields_reported(tmp_path):
    raw_wav1 = tmp_path / "data" / "acoustic" / "raw" / "a.wav"
    raw_wav2 = tmp_path / "data" / "acoustic" / "raw" / "b.wav"
    sha1 = _create_sample_wav(raw_wav1, frames=8000, sr=16000)
    os.makedirs(os.path.dirname(str(raw_wav2)), exist_ok=True)
    sf.write(str(raw_wav2), np.full(8000, 0.25, dtype=np.float32), 16000)
    sha2 = compute_file_sha256(str(raw_wav2))

    meta = {
        "modality": "ACOUSTIC",
        "source_type": "LIVE_HARDWARE",
        "source_mode": "SYNTHETIC SIMULATION",
        "sensor_id": "MIC-01",
        "timestamp": "2026-11-13T18:00:00Z",
        "capture_timestamp_iso": "2026-11-12T00:00:00Z",
        "timestamp_epoch": 1794592800.0,
        "capture_timestamp_epoch": 1794000000.0,
        "sample_rate": 16000,
        "sample_rate_hz": 44100,
        "sample_count": 8000,
        "data_file": "data/acoustic/raw/a.wav",
        "raw_data_path": "data/acoustic/raw/b.wav",
        "data_sha256": sha1,
        "raw_data_sha256": sha2,
    }
    meta_path = tmp_path / "data" / "acoustic" / "metadata" / "conflict.json"
    save_metadata(meta, str(meta_path))

    rec = validate_metadata_file(str(meta_path), str(tmp_path), str(tmp_path / "data"))
    assert rec.validation_status == "INVALID"
    assert rec.source_classification == "INVALID"
    assert len(rec.metadata_inconsistencies) >= 5
    joined = " | ".join(rec.metadata_inconsistencies)
    assert "Conflicting source fields" in joined
    assert "Conflicting timestamps" in joined
    assert "Conflicting sample rate" in joined
    assert "Conflicting data file" in joined
    assert "Conflicting SHA-256" in joined


def test_conflicting_iso_and_epoch_timestamps_detected(tmp_path):
    raw_npy = tmp_path / "data" / "rf" / "raw" / "ts.npy"
    sha = _create_sample_npy(raw_npy, length=512)

    meta = {
        "modality": "RF",
        "source_type": "SYNTHETIC_SIMULATION",
        "sensor_id": "SDR-01 (SYNTHETIC)",
        "timestamp": "2026-11-13T18:00:00Z",
        "timestamp_epoch": 1700000000.0,  # Different year (~2023 vs 2026)
        "sample_rate": 2048000,
        "sample_count": 512,
        "data_file": "data/rf/raw/ts.npy",
        "data_sha256": sha,
    }
    meta_path = tmp_path / "data" / "rf" / "metadata" / "ts.json"
    save_metadata(meta, str(meta_path))

    rec = validate_metadata_file(str(meta_path), str(tmp_path), str(tmp_path / "data"))
    assert rec.validation_status == "INVALID"
    assert rec.timestamp_verified is False
    assert any("Timestamp conflict" in e for e in rec.metadata_inconsistencies)


def test_invalid_timestamp_not_replaced_with_current_time(tmp_path):
    raw_npy = tmp_path / "data" / "rf" / "raw" / "badts.npy"
    sha = _create_sample_npy(raw_npy, length=512)

    meta = {
        "modality": "RF",
        "source_type": "SYNTHETIC_SIMULATION",
        "sensor_id": "SDR-01 (SYNTHETIC)",
        "timestamp": "not-a-valid-timestamp",
        "sample_rate": 2048000,
        "sample_count": 512,
        "data_file": "data/rf/raw/badts.npy",
        "data_sha256": sha,
    }
    meta_path = tmp_path / "data" / "rf" / "metadata" / "badts.json"
    save_metadata(meta, str(meta_path))

    rec = validate_metadata_file(str(meta_path), str(tmp_path), str(tmp_path / "data"))
    assert rec.validation_status == "INVALID"
    assert rec.timestamp_verified is False
    assert rec.capture_timestamp_iso == "not-a-valid-timestamp"


# ---------------------------------------------------------------------------
# 3. CROSS-PLATFORM PATH RESOLUTION
# ---------------------------------------------------------------------------

def test_cross_platform_and_relative_path_resolution(tmp_path):
    proj_root = tmp_path / "workspace"
    target = proj_root / "aetherhound" / "data" / "rf" / "raw" / "capture.npy"
    _create_sample_npy(target, length=1024)
    meta_dir = proj_root / "aetherhound" / "data" / "rf" / "metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)

    # 1. Windows absolute path with backslashes & forward slashes
    for win_p in (
        r"P:\project\aetherhound\data\rf\raw\capture.npy",
        "P:/project/aetherhound/data/rf/raw/capture.npy",
    ):
        res, ok, method = resolve_evidence_path(win_p, str(proj_root), str(proj_root / "aetherhound" / "data"), str(meta_dir))
        assert ok is True
        assert os.path.realpath(res) == os.path.realpath(str(target))
        assert "WINDOWS_TO_LOCAL" in method

    # 2. Linux absolute path from different host
    res, ok, method = resolve_evidence_path(
        "/opt/ci/aetherhound/data/rf/raw/capture.npy",
        str(proj_root),
        str(proj_root / "aetherhound" / "data"),
        str(meta_dir),
    )
    assert ok is True
    assert os.path.realpath(res) == os.path.realpath(str(target))
    assert "LINUX_TO_LOCAL" in method

    # 3. Project-root-relative path
    res, ok, _ = resolve_evidence_path(
        "aetherhound/data/rf/raw/capture.npy",
        str(proj_root),
        str(proj_root / "aetherhound" / "data"),
    )
    assert ok is True
    assert os.path.realpath(res) == os.path.realpath(str(target))

    # 4. Relative with '.' and '..'
    res, ok, _ = resolve_evidence_path(
        "../raw/./capture.npy",
        str(proj_root),
        str(proj_root / "aetherhound" / "data"),
        str(meta_dir),
    )
    assert ok is True
    assert os.path.realpath(res) == os.path.realpath(str(target))

    # 5. Missing file must not falsely resolve to an unrelated directory with same basename
    unrelated = proj_root / "unrelated_folder" / "capture.npy"
    _create_sample_npy(unrelated, length=1024)
    _, ok_wrong, _ = resolve_evidence_path(
        "P:/other/data/rf/raw/missing_capture.npy",
        str(proj_root),
        str(proj_root / "aetherhound" / "data"),
    )
    assert ok_wrong is False

    _, ok_subdir_mismatch, _ = resolve_evidence_path(
        "/other_host/aetherhound/data/other_subdir/capture.npy",
        str(proj_root),
        str(proj_root / "aetherhound" / "data"),
    )
    assert ok_subdir_mismatch is False


def test_linux_style_path_evaluated_on_windows_simulation(tmp_path):
    """Simulate Windows path-join semantics while evaluating a Linux-style metadata path."""
    proj_root = tmp_path / "win_repo"
    target = proj_root / "aetherhound" / "data" / "rf" / "raw" / "win_cap.npy"
    _create_sample_npy(target, length=256)

    with patch("aetherhound.scripts.verify_evidence.os.path.isabs", return_value=False):
        res, ok, method = resolve_evidence_path(
            "/app/aetherhound/data/rf/raw/win_cap.npy",
            str(proj_root),
            str(proj_root / "aetherhound" / "data"),
        )
    assert ok is True
    assert os.path.realpath(res) == os.path.realpath(str(target))
    assert "LINUX_TO_LOCAL" in method


# ---------------------------------------------------------------------------
# 4. INTEGRITY VALIDATION (SHA-256, SAMPLE COUNT, SAMPLE RATE, MISSING)
# ---------------------------------------------------------------------------

def test_integrity_hash_edge_cases(tmp_path):
    raw_npy = tmp_path / "data" / "rf" / "raw" / "h.npy"
    good_sha = _create_sample_npy(raw_npy, length=512)
    meta_dir = tmp_path / "data" / "rf" / "metadata"

    base = {
        "modality": "RF",
        "source_type": "SYNTHETIC_SIMULATION",
        "sensor_id": "SDR-01 (SYNTHETIC)",
        "timestamp": "2026-11-13T18:00:00Z",
        "sample_rate": 2048000,
        "sample_count": 512,
        "data_file": "data/rf/raw/h.npy",
    }

    # Incorrect SHA-256
    m_wrong = dict(base, data_sha256="0" * 64)
    p_wrong = meta_dir / "wrong.json"
    save_metadata(m_wrong, str(p_wrong))
    r_wrong = validate_metadata_file(str(p_wrong), str(tmp_path), str(tmp_path / "data"))
    assert r_wrong.hash_verified is False
    assert r_wrong.sha256_verification_status == "MISMATCH"
    assert r_wrong.file_integrity_status == "FAIL"
    assert r_wrong.validation_status == "INVALID"

    # Malformed SHA-256
    m_mal = dict(base, data_sha256="not-a-valid-hex-digest!")
    p_mal = meta_dir / "mal.json"
    save_metadata(m_mal, str(p_mal))
    r_mal = validate_metadata_file(str(p_mal), str(tmp_path), str(tmp_path / "data"))
    assert r_mal.hash_verified is False
    assert r_mal.sha256_verification_status == "MALFORMED_EXPECTED_HASH"
    assert r_mal.validation_status == "INVALID"

    # Missing SHA-256
    m_miss = dict(base)
    p_miss = meta_dir / "miss.json"
    save_metadata(m_miss, str(p_miss))
    r_miss = validate_metadata_file(str(p_miss), str(tmp_path), str(tmp_path / "data"))
    assert r_miss.hash_verified is False
    assert r_miss.sha256_verification_status == "MISSING_EXPECTED_HASH"
    assert r_miss.validation_status == "INVALID"

    # Correct SHA-256
    m_ok = dict(base, data_sha256=good_sha)
    p_ok = meta_dir / "ok.json"
    save_metadata(m_ok, str(p_ok))
    r_ok = validate_metadata_file(str(p_ok), str(tmp_path), str(tmp_path / "data"))
    assert r_ok.hash_verified is True
    assert r_ok.sha256_verification_status == "MATCH"
    assert r_ok.validation_status == "VERIFIED"


def test_sample_count_vs_byte_size_and_wav_sample_rate_mismatch(tmp_path):
    raw_wav = tmp_path / "data" / "acoustic" / "raw" / "rate_test.wav"
    sha = _create_sample_wav(raw_wav, frames=1000, sr=22050)
    byte_size = os.path.getsize(str(raw_wav))
    assert byte_size != 1000

    # Putting byte_size as sample_count must fail!
    meta_bytes = {
        "modality": "ACOUSTIC",
        "source_type": "SYNTHETIC_SIMULATION",
        "sensor_id": "MIC-01 (VIRTUAL)",
        "timestamp": "2026-11-13T18:00:00Z",
        "sample_rate": 22050,
        "sample_count": byte_size,
        "data_file": "data/acoustic/raw/rate_test.wav",
        "data_sha256": sha,
    }
    p_bytes = tmp_path / "data" / "acoustic" / "metadata" / "bytes.json"
    save_metadata(meta_bytes, str(p_bytes))
    r_bytes = validate_metadata_file(str(p_bytes), str(tmp_path), str(tmp_path / "data"))
    assert r_bytes.samples_verified is False
    assert r_bytes.actual_samples == 1000
    assert r_bytes.validation_status == "INVALID"

    # Sample rate mismatch against WAV header
    meta_sr = dict(meta_bytes, sample_count=1000, sample_rate=48000)
    p_sr = tmp_path / "data" / "acoustic" / "metadata" / "sr_mismatch.json"
    save_metadata(meta_sr, str(p_sr))
    r_sr = validate_metadata_file(str(p_sr), str(tmp_path), str(tmp_path / "data"))
    assert r_sr.sample_rate_verification == "MISMATCH"
    assert r_sr.validation_status == "INVALID"


def test_missing_raw_file_distinguished_from_hash_mismatch(tmp_path):
    meta = {
        "modality": "RF",
        "source_type": "SYNTHETIC_SIMULATION",
        "sensor_id": "SDR-01 (SYNTHETIC)",
        "timestamp": "2026-11-13T18:00:00Z",
        "sample_rate": 2048000,
        "sample_count": 1024,
        "data_file": "data/rf/raw/nonexistent.npy",
        "data_sha256": "a" * 64,
    }
    p_meta = tmp_path / "data" / "rf" / "metadata" / "missing_raw.json"
    save_metadata(meta, str(p_meta))

    r = validate_metadata_file(str(p_meta), str(tmp_path), str(tmp_path / "data"))
    assert r.raw_data_exists is False
    assert r.file_integrity_status == "MISSING"
    assert r.sha256_verification_status == "SKIPPED_MISSING_FILE"
    assert r.validation_status == "INVALID"


# ---------------------------------------------------------------------------
# 5. SOURCE CLASSIFICATION & NO INFERENCE FROM FILENAME / SENSOR ID
# ---------------------------------------------------------------------------

def test_source_classification_strict_rules(tmp_path):
    raw_npy = tmp_path / "data" / "rf" / "raw" / "live_hardware_looking_name.npy"
    sha = _create_sample_npy(raw_npy, length=512)
    meta_dir = tmp_path / "data" / "rf" / "metadata"

    # 1. Unknown source label must NEVER be classified as hardware
    meta_unk = {
        "modality": "RF",
        "source_type": "CUSTOM_UNKNOWN",
        "sensor_id": "RTL-SDR Hardware Dongle",
        "timestamp": "2026-11-13T18:00:00Z",
        "sample_rate": 2048000,
        "sample_count": 512,
        "data_file": "data/rf/raw/live_hardware_looking_name.npy",
        "data_sha256": sha,
    }
    p_unk = meta_dir / "live_hw_sdr_name.json"
    save_metadata(meta_unk, str(p_unk))
    r_unk = validate_metadata_file(str(p_unk), str(tmp_path), str(tmp_path / "data"))
    assert r_unk.source_classification == "INVALID"
    assert r_unk.validation_status == "INVALID"

    # 2. Missing source even with hardware-sounding filename must be UNKNOWN/INVALID, never hardware
    meta_none = dict(meta_unk)
    del meta_none["source_type"]
    p_none = meta_dir / "hardware_capture.json"
    save_metadata(meta_none, str(p_none))
    r_none = validate_metadata_file(str(p_none), str(tmp_path), str(tmp_path / "data"))
    assert r_none.source_classification == "UNKNOWN"
    assert r_none.validation_status == "INVALID"


def test_discovery_across_legacy_and_current_without_duplicates(tmp_path):
    legacy_meta_dir = tmp_path / "data" / "rf" / "metadata"
    new_meta_dir = tmp_path / "aetherhound" / "data" / "acoustic" / "metadata"
    legacy_meta_dir.mkdir(parents=True)
    new_meta_dir.mkdir(parents=True)
    (tmp_path / "unrelated" / "rf" / "metadata").mkdir(parents=True)

    (legacy_meta_dir / "m1.json").write_text("{}", encoding="utf-8")
    (new_meta_dir / "m2.json").write_text("{}", encoding="utf-8")
    (tmp_path / "unrelated" / "rf" / "metadata" / "ignore.json").write_text("{}", encoding="utf-8")

    found, _ = discover_metadata_files(str(tmp_path))
    names = sorted(os.path.basename(p) for p in found)
    assert names == ["m1.json", "m2.json"]


# ---------------------------------------------------------------------------
# 6. NON-DESTRUCTIVE AUDIT REPORT GENERATION
# ---------------------------------------------------------------------------

def test_non_destructive_report_safety_and_cli(tmp_path):
    raw_npy = tmp_path / "data" / "rf" / "raw" / "cap.npy"
    sha = _create_sample_npy(raw_npy, length=512)
    meta = {
        "modality": "RF",
        "source_type": "SYNTHETIC_SIMULATION",
        "sensor_id": "SDR-01 (SYNTHETIC)",
        "timestamp": "2026-11-13T18:00:00Z",
        "sample_rate": 2048000,
        "sample_count": 512,
        "data_file": "data/rf/raw/cap.npy",
        "data_sha256": sha,
    }
    save_metadata(meta, str(tmp_path / "data" / "rf" / "metadata" / "cap.json"))

    # Pre-existing production audit report sentinel
    prod_report = tmp_path / "data" / "evidence_audit_report.json"
    sentinel_content = '{"sentinel": "DO_NOT_OVERWRITE"}'
    prod_report.write_text(sentinel_content, encoding="utf-8")

    # 1. Default run without overwrite must NOT overwrite existing production report
    res_safe = run_full_audit(str(tmp_path), write_report=True, sync_public=False)
    assert prod_report.read_text(encoding="utf-8") == sentinel_content
    assert res_safe["report_output_path"] is not None
    assert os.path.abspath(res_safe["report_output_path"]) != os.path.abspath(str(prod_report))
    assert os.path.exists(res_safe["report_output_path"])
    assert str(prod_report) in res_safe["preserved_existing_reports"]

    # 2. Explicit output directory
    out_dir = tmp_path / "custom_out"
    res_dir = run_full_audit(str(tmp_path), write_report=True, output_dir=str(out_dir))
    assert prod_report.read_text(encoding="utf-8") == sentinel_content
    assert os.path.abspath(res_dir["report_output_path"]) == os.path.abspath(str(out_dir / "evidence_audit_report.json"))
    assert os.path.exists(res_dir["report_output_path"])

    # 3. Test mode uses temp dir cleanly
    res_tmp = run_full_audit(str(tmp_path), write_report=True, test_mode=True)
    assert prod_report.read_text(encoding="utf-8") == sentinel_content
    assert os.path.exists(res_tmp["report_output_path"])
    assert str(tmp_path) not in res_tmp["report_output_path"]

    # 4. Explicit output path
    explicit_file = tmp_path / "explicit" / "my_report.json"
    res_exp = run_full_audit(str(tmp_path), write_report=True, output_path=str(explicit_file))
    assert prod_report.read_text(encoding="utf-8") == sentinel_content
    assert os.path.exists(str(explicit_file))
    assert res_exp["report_output_path"] == str(explicit_file)

    # 5. CLI --test-mode does not touch existing production reports
    proc = subprocess.run(
        [sys.executable, "aetherhound/scripts/verify_evidence.py", "--base-dir", str(tmp_path), "--test-mode", "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    cli_json = json.loads(proc.stdout)
    assert cli_json["overall_result"] == "VERIFIED"
    assert prod_report.read_text(encoding="utf-8") == sentinel_content
