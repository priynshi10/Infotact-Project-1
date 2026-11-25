"""
Forensic Signal Snapshot Archiver & Cryptographic Chain-of-Custody Manifest Generator.
Captures synchronized raw RF I/Q, acoustic WAV, and STFT spectrogram matrices
and seals them with SHA-256 integrity digests for incident post-mortems and legal compliance.
"""

import os
import json
import hashlib
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any
import wave


class ForensicSignalArchiver:
    """Archives raw signal evidence to disk with cryptographic chain-of-custody metadata."""

    def __init__(self, base_dir: str = "data/forensics"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    @staticmethod
    def compute_sha256(filepath: str) -> str:
        """Compute SHA-256 digest of an evidence file."""
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def export_evidence_bundle(
        self,
        incident_id: str,
        audio_samples: np.ndarray,
        sample_rate: int,
        rf_iq_samples: np.ndarray,
        spectrogram_patch: np.ndarray,
        metadata: Dict[str, Any]
    ) -> str:
        """Export complete evidence bundle with SHA-256 checksums and manifest."""
        bundle_dir = os.path.join(self.base_dir, incident_id)
        os.makedirs(bundle_dir, exist_ok=True)

        # 1. Save Acoustic WAV
        wav_path = os.path.join(bundle_dir, "acoustic_evidence.wav")
        int_audio = np.clip(audio_samples * 32767.0, -32768, 32767).astype(np.int16)
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(int_audio.tobytes())

        # 2. Save Raw RF I/Q Array
        rf_path = os.path.join(bundle_dir, "rf_iq_evidence.npy")
        np.save(rf_path, rf_iq_samples.astype(np.complex64))

        # 3. Save STFT Spectrogram Patch
        spec_path = os.path.join(bundle_dir, "spectrogram_patch.npy")
        np.save(spec_path, spectrogram_patch.astype(np.float32))

        # 4. Generate Chain of Custody Manifest
        manifest = {
            "incident_id": incident_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "evidence_files": {
                "acoustic_wav": {
                    "filename": "acoustic_evidence.wav",
                    "sha256": self.compute_sha256(wav_path),
                    "sample_rate": sample_rate,
                    "sample_count": len(audio_samples)
                },
                "rf_iq": {
                    "filename": "rf_iq_evidence.npy",
                    "sha256": self.compute_sha256(rf_path),
                    "dimensions": list(rf_iq_samples.shape)
                },
                "spectrogram": {
                    "filename": "spectrogram_patch.npy",
                    "sha256": self.compute_sha256(spec_path),
                    "dimensions": list(spectrogram_patch.shape)
                }
            },
            "sigint_telemetry": metadata
        }

        manifest_path = os.path.join(bundle_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return bundle_dir
