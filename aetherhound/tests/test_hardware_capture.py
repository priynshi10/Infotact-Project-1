import json

import numpy as np
import pytest
import soundfile as sf

from aetherhound.core.evidence_metadata import (
    SOURCE_TYPE_LIVE_HARDWARE,
    SOURCE_TYPE_SYNTHETIC_SIMULATION,
    compute_file_sha256,
    validate_metadata,
)
from aetherhound.dsp.acoustic_processor import AcousticProcessor
from aetherhound.dsp.rf_processor import RFProcessor
from aetherhound.hardware import acoustic_capture
from aetherhound.hardware.acoustic_capture import (
    AcousticCaptureDevice,
    AudioChunk,
    capture_recording as capture_audio,
)
from aetherhound.hardware.config import AcousticConfig, RFConfig
from aetherhound.hardware.rf_capture import IQSampleWindow, capture_recording as capture_rf


class MockRFDevice:
    synthetic_mode = False
    _last_error = "RTL-SDR unavailable"

    def __init__(self, window=None, starts=True):
        self.window = window
        self.starts = starts
        self.stopped = False

    def start(self):
        return self.starts

    def get_window(self, timeout=0.2):
        window, self.window = self.window, None
        return window

    def stop(self):
        self.stopped = True


def test_rf_capture_writes_iq_spectrum_hash_and_provenance(tmp_path):
    config = RFConfig(
        center_freq_hz=433_920_000,
        sample_rate_hz=225_000,
        fft_size=128,
        samples_per_window=128,
    )
    samples = np.exp(2j * np.pi * np.arange(256) / 16).astype(np.complex64)
    window = IQSampleWindow(
        samples,
        1794500000.0,
        config.center_freq_hz,
        config.sample_rate_hz,
        source_type=SOURCE_TYPE_LIVE_HARDWARE,
    )
    device = MockRFDevice(window)

    result = capture_rf(config, 0.01, str(tmp_path), device=device)
    raw = np.load(result["raw_iq_file"])
    spectrum = np.load(result["spectrum_file"])
    metadata = json.loads(open(result["metadata_file"], encoding="utf-8").read())
    valid, errors = validate_metadata(metadata)

    assert device.stopped
    assert np.array_equal(raw, samples)
    assert len(spectrum["frequencies_hz"]) == config.fft_size
    assert result["sample_count"] == len(samples)
    assert metadata["source_type"] == SOURCE_TYPE_LIVE_HARDWARE
    assert metadata["capture_status"] == "COMPLETED"
    assert metadata["data_sha256"] == compute_file_sha256(result["raw_iq_file"])
    assert metadata["spectrum_sha256"] == compute_file_sha256(result["spectrum_file"])
    assert valid, errors
    processed = RFProcessor(config).process_window(
        IQSampleWindow(
            raw,
            1794500000.0,
            config.center_freq_hz,
            config.sample_rate_hz,
            source_type=SOURCE_TYPE_LIVE_HARDWARE,
        )
    )
    assert processed.is_synthetic is False
    assert processed.source_type == SOURCE_TYPE_LIVE_HARDWARE


def test_rf_capture_reports_unavailable_device(tmp_path):
    with pytest.raises(RuntimeError, match="RTL-SDR unavailable"):
        capture_rf(RFConfig(), 0.01, str(tmp_path), device=MockRFDevice(starts=False))


def test_rf_capture_rejects_nonpositive_duration():
    with pytest.raises(ValueError, match="duration"):
        capture_rf(RFConfig(), 0)


def test_audio_capture_writes_wav_measurements_and_provenance(tmp_path, monkeypatch):
    config = AcousticConfig(sample_rate_hz=16000, chunk_size=256)
    device = AcousticCaptureDevice(config)
    samples = np.array([0.25, -0.5, 0.75, -1.0] * 64, dtype=np.float32)
    monkeypatch.setattr(device, "start", lambda: True)
    monkeypatch.setattr(device, "stop", lambda: None)
    start_recording = device.start_recording

    def append_mock_capture():
        start_recording()
        with device._recording_lock:
            device._recording_buffer.append(samples.copy())

    monkeypatch.setattr(device, "start_recording", append_mock_capture)
    monkeypatch.setattr(acoustic_capture.time, "sleep", lambda _: None)

    result = capture_audio(config, 0.01, str(tmp_path), device=device, sensor_id="MOCK-MIC")
    wav_data, sample_rate = sf.read(result["audio_file"])
    metadata = json.loads(open(result["metadata_file"], encoding="utf-8").read())
    valid, errors = validate_metadata(metadata)

    assert sample_rate == config.sample_rate_hz
    assert sf.info(result["audio_file"]).subtype == "PCM_16"
    assert len(wav_data) == len(samples)
    assert metadata["source_type"] == SOURCE_TYPE_LIVE_HARDWARE
    assert metadata["microphone_id"] == "MOCK-MIC"
    assert metadata["capture_status"] == "COMPLETED"
    assert metadata["metrics"]["rms_energy"] == pytest.approx(np.sqrt(np.mean(samples**2)), rel=1e-4)
    assert metadata["metrics"]["peak_amplitude"] == pytest.approx(1.0)
    assert metadata["metrics"]["zero_crossing_rate"] > 0
    assert metadata["metrics"]["match_score"] is None
    assert metadata["data_sha256"] == compute_file_sha256(result["audio_file"])
    assert valid, errors
    processed = AcousticProcessor(config).process_chunk(
        AudioChunk(wav_data.astype(np.float32), 1794500000.0, sample_rate, config.channels)
    )
    assert len(processed.raw_samples) == len(wav_data)


def test_audio_capture_reports_unavailable_microphone(tmp_path):
    device = AcousticCaptureDevice(AcousticConfig())
    device._last_error = "No input device"
    device.start = lambda: False

    with pytest.raises(RuntimeError, match="No input device"):
        capture_audio(device.config, 0.01, str(tmp_path), device=device)


def test_synthetic_acquisition_is_not_reported_as_connected():
    assert AcousticCaptureDevice(synthetic_mode=True).is_connected is False
