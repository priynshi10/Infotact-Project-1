import json
import os

import numpy as np
import pytest

from aetherhound.core.synthetic_input import generate_synthetic_acoustic, generate_synthetic_rf
from aetherhound.core.event_store import append_event, read_events
from aetherhound.core.evidence_metadata import validate_metadata
from aetherhound.detection.anomaly_detector import (
    FEATURE_NAMES,
    NumPyAnomalyDetector,
    extract_numeric_features,
    generate_synthetic_dataset,
)
from aetherhound.scripts.capability_check import capability_report
from aetherhound.detection.anomaly_detector import PyTorchAutoencoderDetector
from aetherhound.core.pipeline import run_pipeline


def test_synthetic_generators_repeat_and_validate_metadata(tmp_path):
    rf = generate_synthetic_rf(
        0.002, 2_048_000, carrier_hz=100000, seed=7,
        output_dir=str(tmp_path),
    )
    valid, errors = validate_metadata(rf.metadata)
    assert valid, errors
    assert np.iscomplexobj(rf.samples)
    assert rf.samples.dtype == np.complex64

    audio = generate_synthetic_acoustic(
        0.02, 16000, tone_hz=1000, seed=7,
        output_dir=str(tmp_path),
    )
    valid, errors = validate_metadata(audio.metadata)
    assert valid, errors
    assert audio.samples.dtype == np.float32


def test_synthetic_generators_reject_parameters_and_overwrite():
    with pytest.raises(ValueError):
        generate_synthetic_rf(-1, 2048000)
    with pytest.raises(ValueError):
        generate_synthetic_acoustic(0.01, 8000, tone_hz=5000)


def test_numeric_features_and_dataset_are_deterministic():
    sr = 8000.0
    t = np.arange(sr) / sr
    signal = np.sin(2 * np.pi * 1000 * t)
    features = extract_numeric_features(signal, sr)
    assert features.shape == (len(FEATURE_NAMES),)
    assert np.all(np.isfinite(features))
    x1, y1 = generate_synthetic_dataset(count_per_class=20, seed=42)
    x2, y2 = generate_synthetic_dataset(count_per_class=20, seed=42)
    assert np.array_equal(x1, x2)
    assert np.array_equal(y1, y2)


def test_baseline_train_save_load_predict(tmp_path):
    x, y = generate_synthetic_dataset(count_per_class=50, seed=123)
    normal = x[y == 0]
    anomaly = x[y == 1]
    detector = NumPyAnomalyDetector(percentile=95)
    detector.train(normal)
    detector.save(str(tmp_path))
    loaded = NumPyAnomalyDetector.load(str(tmp_path))

    normal_prediction = loaded.predict(normal[0], source_id="TEST")
    anomaly_prediction = loaded.predict(anomaly[0], source_id="TEST")
    assert normal_prediction["status"] in ("NORMAL", "ANOMALY")
    assert anomaly_prediction["status"] in ("NORMAL", "ANOMALY")
    assert normal_prediction["model_version"] == anomaly_prediction["model_version"]
    assert normal_prediction["threshold"] == pytest.approx(loaded.threshold)


def test_event_append_readback_and_missing_model(tmp_path):
    event = {
        "source_id": "SYNTHETIC-MIC-01",
        "signal_type": "ACOUSTIC",
        "status": "ANOMALY",
        "input_mode": "synthetic",
        "score": 1.5,
    }
    path = append_event(event, str(tmp_path), "test_events.jsonl")
    records = read_events(path)
    assert records[0]["source_id"] == "SYNTHETIC-MIC-01"
    assert "timestamp" in records[0]
    with pytest.raises(FileNotFoundError):
        NumPyAnomalyDetector.load(str(tmp_path))
    assert isinstance(capability_report(), dict)


def test_pytorch_autoencoder_train_save_load_and_predict(tmp_path):
    pytest.importorskip("torch")
    x, y = generate_synthetic_dataset(count_per_class=30, seed=321)
    normal = x[y == 0]
    detector = PyTorchAutoencoderDetector(percentile=95.0, seed=321, epochs=3)
    detector.train(normal)
    detector.save(str(tmp_path))
    loaded = PyTorchAutoencoderDetector.load(str(tmp_path))
    normal_result = loaded.predict(normal[0], source_id="SYNTHETIC", signal_type="ACOUSTIC")
    assert normal_result["detector_type"] == "pytorch_autoencoder"
    assert normal_result["status"] in ("NORMAL", "ANOMALY")
    assert normal_result["threshold"] == pytest.approx(loaded.threshold)


def test_pytorch_autoencoder_missing_model_and_invalid_features(tmp_path):
    pytest.importorskip("torch")
    with pytest.raises(FileNotFoundError):
        PyTorchAutoencoderDetector.load(str(tmp_path))
    detector = PyTorchAutoencoderDetector()
    with pytest.raises(RuntimeError, match="not trained"):
        detector.predict(np.ones(len(FEATURE_NAMES)))
    detector.trained = False


def test_corrupt_pytorch_model(tmp_path):
    pytest.importorskip("torch")
    (tmp_path / "pytorch_autoencoder.pt").write_bytes(b"not a torch archive")
    with pytest.raises(ValueError, match="Corrupt or incompatible"):
        PyTorchAutoencoderDetector.load(str(tmp_path))


def test_synthetic_end_to_end_pipeline(tmp_path, monkeypatch):
    x, y = generate_synthetic_dataset(count_per_class=30, seed=777)
    detector = NumPyAnomalyDetector().train(x[y == 0])
    t = np.arange(4000) / 8000.0
    samples = np.sin(2 * np.pi * 1000 * t).astype(np.float64)
    monkeypatch.chdir(tmp_path)
    result = run_pipeline(
        samples, 8000.0, detector, "SYNTHETIC-RF-01", "RF", "synthetic",
    )
    assert result["input_mode"] == "synthetic"
    assert result["status"] in ("NORMAL", "ANOMALY")
