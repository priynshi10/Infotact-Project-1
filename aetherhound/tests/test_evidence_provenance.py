"""
Unit & Integration Tests for Day 1 Evidence Provenance & Signal Validation System.
Tests run completely offline without physical RTL-SDR or microphone hardware.
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

from aetherhound.core.evidence_metadata import (
    MODALITY_ACOUSTIC,
    MODALITY_FAN_SIMULATION,
    MODALITY_RF,
    SOURCE_TYPE_LIVE_HARDWARE,
    SOURCE_TYPE_RECORDED_HARDWARE,
    SOURCE_TYPE_SYNTHETIC_SIMULATION,
    build_acoustic_metadata,
    build_fan_simulation_metadata,
    build_rf_metadata,
    compute_array_sha256,
    compute_file_sha256,
    generate_capture_id,
    load_metadata,
    save_metadata,
    validate_metadata,
)
from aetherhound.dsp.plot_utils import (
    save_acoustic_waveform_plot,
    save_fan_rpm_plot,
    save_rf_spectrum_plot,
)
from aetherhound.dsp.provenance import load_provenance_metadata
from aetherhound.hardware.acoustic_capture import AcousticCaptureDevice
from aetherhound.hardware.config import AcousticConfig, RFConfig
from aetherhound.hardware.rf_capture import IQSampleWindow, RFCaptureDevice
from aetherhound.scripts.verify_evidence import run_full_audit


def test_rf_plot_provenance_construction_and_serialization(tmp_path):
    output_path = tmp_path / "data" / "plots" / "rf_spectrum" / "rf.png"
    frequencies = np.linspace(433_000_000, 434_000_000, 8)
    spectrum = np.linspace(-90, -70, 8)
    raw_iq = np.ones(8, dtype=np.complex64)

    _, provenance = save_rf_spectrum_plot(
        frequencies,
        spectrum,
        noise_floor_db=-90.0,
        output_path=str(output_path),
        raw_iq_samples=raw_iq,
        capture_id="RF-test",
        rf_gain="auto",
        fft_size=8,
    )

    serialized = provenance.to_dict()
    assert serialized["capture_id"] == "RF-test"
    assert serialized["modality"] == MODALITY_RF
    assert serialized["source_type"] == SOURCE_TYPE_SYNTHETIC_SIMULATION
    assert serialized["data_source"] == "SYNTHETIC SIMULATION"
    assert serialized["rf_gain"] == "auto"
    assert serialized["fft_size"] == 8
    assert serialized["sample_count"] == len(raw_iq)
    assert serialized["raw_data_sha256"] == compute_array_sha256(raw_iq)
    assert serialized["device_verified"] is False


def test_acoustic_plot_provenance_construction(tmp_path):
    output_path = tmp_path / "data" / "plots" / "acoustic_waveform" / "acoustic.png"
    times = np.arange(8, dtype=np.float64) / 8
    audio = np.zeros((8, 2), dtype=np.float32)
    envelope = np.linspace(0, 1, 8)

    _, provenance = save_acoustic_waveform_plot(
        times,
        audio,
        envelope,
        str(output_path),
        sample_rate_hz=8,
        channels=2,
        audio_format="float32",
        capture_id="MIC-test",
    )

    serialized = provenance.to_dict()
    assert serialized["capture_id"] == "MIC-test"
    assert serialized["modality"] == MODALITY_ACOUSTIC
    assert serialized["channels"] == 2
    assert serialized["audio_format"] == "float32"
    assert serialized["sample_count"] == len(audio)
    assert serialized["center_freq_hz"] is None
    assert serialized["device_verified"] is False


def test_fan_simulation_provenance_remains_synthetic(tmp_path):
    output_path = tmp_path / "data" / "plots" / "fan_rpm" / "fan.png"
    times = np.linspace(0.0, 1.0, 6)
    rpms = np.full_like(times, 1200.0)
    states = np.array([False, True, True, False, False, False])
    sim_parameters = {"message": "SOS", "base_rpm": 1200.0}

    _, provenance = save_fan_rpm_plot(
        times,
        rpms,
        states,
        str(output_path),
        capture_id="FANSIM-test",
        simulation_parameters=sim_parameters,
    )

    serialized = provenance.to_dict()
    assert serialized["capture_id"] == "FANSIM-test"
    assert serialized["modality"] == MODALITY_FAN_SIMULATION
    assert serialized["source_mode"] == "SYNTHETIC SIMULATION"
    assert serialized["source_type"] == SOURCE_TYPE_SYNTHETIC_SIMULATION
    assert serialized["data_source"] == "SYNTHETIC SIMULATION"
    assert serialized["simulation_parameters"] == sim_parameters
    assert serialized["device_verified"] is False

    loaded = load_provenance_metadata(str(output_path.with_suffix(".json")))
    assert loaded is not None
    assert loaded.to_dict() == serialized


def test_load_provenance_metadata_supports_legacy_json(tmp_path):
    legacy_data = {
        "plot_path": "plots/legacy.png",
        "source_mode": "LIVE HARDWARE",
        "sensor_id": "SDR-01",
        "capture_timestamp_iso": "2026-11-12T10:00:00Z",
        "capture_timestamp_epoch": 1794477600.0,
        "sample_rate_hz": 2_048_000.0,
        "center_freq_hz": 433_920_000.0,
        "recording_duration_sec": 1.0,
        "sample_count": 2_048_000,
        "raw_data_path": "data/rf/raw/legacy.npy",
        "raw_data_sha256": "a" * 64,
        "device_verified": True,
        "detection_event_type": "RF_SPECTRAL_ANOMALY",
        "metrics": {"peak_freq_hz": 433_920_000.0},
        "notes": "Legacy capture",
    }
    metadata_path = tmp_path / "legacy.json"
    metadata_path.write_text(json.dumps(legacy_data), encoding="utf-8")

    loaded = load_provenance_metadata(str(metadata_path))

    assert loaded is not None
    assert loaded.plot_path == legacy_data["plot_path"]
    assert loaded.capture_timestamp_epoch == legacy_data["capture_timestamp_epoch"]
    assert loaded.device_verified is True
    assert loaded.metrics == legacy_data["metrics"]
    assert loaded.notes == legacy_data["notes"]
    assert loaded.capture_id is None
    assert loaded.modality is None
    assert loaded.simulation_parameters is None


def test_load_provenance_metadata_rejects_missing_required_fields(tmp_path):
    metadata_path = tmp_path / "malformed.json"
    metadata_path.write_text(json.dumps({"plot_path": "plots/incomplete.png"}), encoding="utf-8")

    with pytest.raises(ValueError, match="missing required fields"):
        load_provenance_metadata(str(metadata_path))


def test_metadata_generation_and_unique_capture_ids():
    id1 = generate_capture_id("RF")
    id2 = generate_capture_id("RF")
    assert id1 != id2
    assert id1.startswith("RF-")

    rf_meta = build_rf_metadata(
        sensor_id="SDR-01",
        source_type=SOURCE_TYPE_LIVE_HARDWARE,
        center_freq_hz=433_920_000.0,
        sample_rate_hz=2_048_000.0,
        rf_gain="auto",
        sample_count=16384,
        fft_size=2048,
        data_file="data/rf/raw/cap1.npy",
        acquisition_mode="RTL-SDR Hardware IQ Stream",
    )
    ok, errs = validate_metadata(rf_meta)
    assert ok is True, f"Unexpected validation errors: {errs}"
    assert rf_meta["data_source"] == "LIVE HARDWARE"
    assert rf_meta["rf_gain"] == "auto"
    assert rf_meta["fft_size"] == 2048

    ac_meta = build_acoustic_metadata(
        sensor_id="MIC-01",
        source_type=SOURCE_TYPE_SYNTHETIC_SIMULATION,
        sample_rate_hz=44100,
        channels=1,
        audio_format="float32",
        sample_count=88200,
        data_file="data/acoustic/raw/mic1.wav",
        acquisition_mode="Virtual Receiver Stream",
    )
    ok, errs = validate_metadata(ac_meta)
    assert ok is True, f"Unexpected validation errors: {errs}"
    assert ac_meta["data_source"] == "SYNTHETIC SIMULATION"
    assert ac_meta["duration_sec"] == 2.0


def test_required_metadata_validation_failures():
    bad_meta = {
        "capture_id": "RF-123",
        "modality": MODALITY_RF,
        # Missing sensor_id, timestamp, rf_gain, fft_size, etc.
        "source_type": SOURCE_TYPE_LIVE_HARDWARE,
        "data_source": "LIVE HARDWARE",
        "sample_rate": -100,
        "sample_count": 0,
    }
    ok, errs = validate_metadata(bad_meta)
    assert ok is False
    assert any("sensor_id" in e for e in errs)
    assert any("rf_gain" in e for e in errs)
    assert any("sample_rate must be > 0" in e for e in errs)
    assert any("sample_count must be > 0" in e for e in errs)


def test_incorrect_source_labels_and_conflict_detection():
    # 1. Invalid source_type
    bad_source = build_acoustic_metadata(
        sensor_id="MIC-01",
        source_type="RANDOM_UNKNOWN_SOURCE",
        sample_rate_hz=44100,
        channels=1,
        audio_format="float32",
        sample_count=44100,
        data_file="test.wav",
        acquisition_mode="PyAudio",
    )
    ok, errs = validate_metadata(bad_source)
    assert ok is False
    assert any("Invalid source_type" in e for e in errs)

    # 2. Live hardware source_type paired with synthetic sensor name
    spoofed = build_rf_metadata(
        sensor_id="SDR-01 (SYNTHETIC IQ BUFFER)",
        source_type=SOURCE_TYPE_LIVE_HARDWARE,
        center_freq_hz=433_920_000.0,
        sample_rate_hz=2_048_000.0,
        rf_gain="auto",
        sample_count=16384,
        fft_size=2048,
        data_file="test.npy",
        acquisition_mode="RTL-SDR Hardware IQ Stream",
    )
    ok, errs = validate_metadata(spoofed)
    assert ok is False
    assert any("Source label conflict" in e for e in errs)

    # 3. Fan simulation falsely labeled LIVE_HARDWARE without tachometer
    fan_spoof = build_fan_simulation_metadata(
        sensor_id="FAN-01",
        sample_rate_hz=50.0,
        sample_count=100,
        duration_sec=2.0,
        data_file="fan.csv",
        simulation_parameters={"base_rpm": 1200},
        source_type=SOURCE_TYPE_LIVE_HARDWARE,
    )
    ok, errs = validate_metadata(fan_spoof)
    assert ok is False
    assert any("tachometer" in e.lower() for e in errs)


def test_verify_evidence_missing_data_file(tmp_path):
    data_dir = tmp_path / "data"
    meta_dir = data_dir / "rf" / "metadata"
    meta_dir.mkdir(parents=True)

    missing_npy = data_dir / "rf" / "raw" / "does_not_exist.npy"
    meta = build_rf_metadata(
        sensor_id="SDR-01",
        source_type=SOURCE_TYPE_SYNTHETIC_SIMULATION,
        center_freq_hz=433_920_000.0,
        sample_rate_hz=2_048_000.0,
        rf_gain="auto",
        sample_count=16384,
        fft_size=2048,
        data_file=str(missing_npy),
        acquisition_mode="Synthetic Complex IQ Simulation",
    )
    save_metadata(meta, str(meta_dir / "cap.json"))

    report = run_full_audit(str(tmp_path), data_dir=str(data_dir), write_report=True, sync_public=False)
    assert report["overall_result"] == "INVALID"
    assert report["failed_or_orphaned_count"] == 1
    rec = report["plots"][0]
    assert rec["raw_data_exists"] is False
    assert rec["validation_status"] == "INVALID"


def test_verify_evidence_invalid_sample_count_and_hash(tmp_path):
    data_dir = tmp_path / "data"
    raw_dir = data_dir / "acoustic" / "raw"
    meta_dir = data_dir / "acoustic" / "metadata"
    raw_dir.mkdir(parents=True)
    meta_dir.mkdir(parents=True)

    wav_path = raw_dir / "mic_cap.wav"
    actual_audio = np.zeros(22050, dtype=np.float32)  # 0.5s
    sf.write(str(wav_path), actual_audio, 44100)
    wav_hash = compute_file_sha256(str(wav_path))

    # Intentionally record wrong sample count (44100 instead of 22050)
    meta = build_acoustic_metadata(
        sensor_id="MIC-01",
        source_type=SOURCE_TYPE_LIVE_HARDWARE,
        sample_rate_hz=44100,
        channels=1,
        audio_format="float32",
        sample_count=44100,
        data_file=str(wav_path),
        acquisition_mode="PyAudio Non-Blocking Microphone Stream",
        data_sha256=wav_hash,
    )
    save_metadata(meta, str(meta_dir / "mic_cap.json"))

    report = run_full_audit(str(tmp_path), data_dir=str(data_dir), write_report=True, sync_public=False)
    assert report["overall_result"] == "INVALID"
    rec = report["plots"][0]
    assert rec["raw_data_exists"] is True
    assert rec["samples_verified"] is False
    assert rec["actual_samples"] == 22050
    assert any("MISMATCH" in r for r in rec["failure_reasons"])


def test_synthetic_vs_hardware_metadata_handling_with_mocked_devices(tmp_path):
    data_dir = tmp_path / "data"

    # 1. Mock hardware IQ window saved by RFCaptureDevice
    rf_dev = RFCaptureDevice(RFConfig(), synthetic_mode=False)
    hw_iq = (np.ones(16384, dtype=np.complex64) * 0.1)
    hw_win = IQSampleWindow(
        samples=hw_iq,
        timestamp=1794500000.0,
        center_freq_hz=433_920_000.0,
        sample_rate_hz=2_048_000.0,
        is_synthetic=False,
        window_id=1,
        source_type=SOURCE_TYPE_LIVE_HARDWARE,
    )
    rf_npy = data_dir / "rf" / "raw" / "hw_capture.npy"
    rf_meta_json = data_dir / "rf" / "metadata" / "hw_capture.json"
    rf_dev.save_window_with_metadata(hw_win, str(rf_npy), str(rf_meta_json), sensor_id="SDR-01")

    # 2. Mock physical microphone recording saved by AcousticCaptureDevice
    mic_dev = AcousticCaptureDevice(AcousticConfig(), synthetic_mode=False)
    mic_dev.start_recording()
    with mic_dev._recording_lock:
        mic_dev._recording_buffer.append(np.zeros(44100, dtype=np.float32))
    ac_wav = data_dir / "acoustic" / "raw" / "hw_mic.wav"
    ac_meta_json = data_dir / "acoustic" / "metadata" / "hw_mic.json"
    saved = mic_dev.stop_and_save_recording(str(ac_wav), str(ac_meta_json), sensor_id="MIC-01")
    assert saved is True

    # 3. Synthetic fan RPM plot & metadata
    rpm_plot = data_dir / "plots" / "acoustic_spectrogram" / "sim_rpm.png"
    times = np.linspace(0.0, 2.0, 100)
    rpms = np.full_like(times, 1200.0)
    states = np.zeros_like(times, dtype=bool)
    save_fan_rpm_plot(times, rpms, states, str(rpm_plot), source_mode="SYNTHETIC SIMULATION")

    report = run_full_audit(str(tmp_path), data_dir=str(data_dir), write_report=True, sync_public=False)
    assert report["overall_result"] == "VERIFIED"
    assert report["audit_passed"] is True
    assert report["hardware_derived_count"] == 2
    assert report["synthetic_simulation_count"] == 1
    assert report["failed_or_orphaned_count"] == 0

    # Check distinction in report records
    by_mod = {p["modality"]: p for p in report["plots"]}
    assert by_mod[MODALITY_RF]["source_mode"] == "LIVE HARDWARE"
    assert "RUNTIME ATTESTED ONLY" in by_mod[MODALITY_RF]["hardware_provenance_note"]
    assert by_mod[MODALITY_ACOUSTIC]["source_mode"] == "LIVE HARDWARE"
    assert by_mod[MODALITY_FAN_SIMULATION]["source_mode"] == "SYNTHETIC SIMULATION"
    assert "not physical hardware" in by_mod[MODALITY_FAN_SIMULATION]["hardware_provenance_note"].lower()


def test_orphan_plot_detection_and_partial_verification(tmp_path):
    data_dir = tmp_path / "data"
    plot_dir = data_dir / "plots" / "rf_spectrum"
    plot_dir.mkdir(parents=True)

    # Create an untraced static PNG with no metadata
    orphan_png = plot_dir / "fake_static_chart.png"
    orphan_png.write_bytes(b"\x89PNG\r\n\x1a\n")

    report = run_full_audit(str(tmp_path), data_dir=str(data_dir), write_report=True, sync_public=False)
    assert report["overall_result"] == "INVALID"
    assert report["failed_or_orphaned_count"] == 1
    assert report["plots"][0]["modality"] == "ORPHAN_PLOT"
    assert report["plots"][0]["validation_status"] == "INVALID"
