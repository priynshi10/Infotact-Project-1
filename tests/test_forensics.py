"""
Unit tests for Forensic Signal Snapshot Archiver & Cryptographic Manifest Integrity.
"""

import os
import json
import numpy as np
import pytest
from aetherhound.dsp.forensics import ForensicSignalArchiver


def test_forensic_bundle_generation(tmp_path):
    archiver = ForensicSignalArchiver(base_dir=str(tmp_path))
    audio = np.random.randn(4800).astype(np.float32)
    rf_iq = (np.random.randn(1024) + 1j * np.random.randn(1024)).astype(np.complex64)
    spec = np.random.rand(40, 64).astype(np.float32)

    bundle_dir = archiver.export_evidence_bundle(
        incident_id="INC-AUDIT-01",
        audio_samples=audio,
        sample_rate=48000,
        rf_iq_samples=rf_iq,
        spectrogram_patch=spec,
        metadata={"rack": "RACK-02", "snr_db": 15.2}
    )

    assert os.path.isdir(bundle_dir)
    manifest_path = os.path.join(bundle_dir, "manifest.json")
    assert os.path.isfile(manifest_path)

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["incident_id"] == "INC-AUDIT-01"
    assert "acoustic_wav" in manifest["evidence_files"]
    assert len(manifest["evidence_files"]["acoustic_wav"]["sha256"]) == 64
    assert manifest["sigint_telemetry"]["rack"] == "RACK-02"
