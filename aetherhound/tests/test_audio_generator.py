"""
Unit tests for Synthetic Fan Audio Generator and Fan Pattern Simulator.
"""

import os
import json
import numpy as np
import pytest
import soundfile as sf

from aetherhound.core.evidence_metadata import (
    SOURCE_TYPE_SYNTHETIC_SIMULATION,
    compute_file_sha256,
    validate_metadata,
)
from aetherhound.dsp.acoustic_processor import AcousticProcessor
from aetherhound.hardware.acoustic_capture import AudioChunk
from aetherhound.hardware.config import AcousticConfig, MorseConfig
from aetherhound.mock_malware.audio_generator import SyntheticFanAudioGenerator
from aetherhound.mock_malware.fan_pattern_simulator import FanPatternSimulator
from aetherhound.detection.morse_detector import RealtimeMorseDetector


def test_fan_rpm_timeline_generation():
    cfg = MorseConfig(dot_duration_sec=0.1, dash_duration_sec=0.3, base_rpm=1200, low_rpm=900, high_rpm=1800)
    sim = FanPatternSimulator(cfg)
    times, rpms, states, events = sim.generate_timeline("SOS", time_step_sec=0.01)

    assert len(times) > 0
    assert len(rpms) == len(times)
    assert len(states) == len(times)
    assert len(events) >= 17

    # RPMS should stay within bounds
    assert np.all(rpms >= 850.0)
    assert np.all(rpms <= 1850.0)


def test_synthetic_audio_generation(tmp_path):
    cfg = MorseConfig(dot_duration_sec=0.05, dash_duration_sec=0.15)
    generator = SyntheticFanAudioGenerator(cfg, sample_rate_hz=16000)

    out_file = str(tmp_path / "test_fan.wav")
    res = generator.generate_synthetic_audio(message="E", lead_in_sec=0.2, lead_out_sec=0.2, output_wav_path=out_file)

    assert res.is_synthetic is True
    assert res.sample_rate_hz == 16000
    assert len(res.audio) > 0
    assert os.path.exists(out_file)

    # Check WAV file readable
    data, sr = sf.read(out_file)
    assert sr == 16000
    assert len(data) == len(res.audio)


def test_fan_morse_cli_exports_simulation_only_artifacts(tmp_path, monkeypatch):
    from aetherhound.mock_malware import fan_pattern_simulator

    monkeypatch.setattr(
        "sys.argv",
        [
            "fan_pattern_simulator",
            "--message",
            "SOS",
            "--output-dir",
            str(tmp_path),
            "--sample-rate",
            "16000",
            "--time-step",
            "0.05",
        ],
    )
    fan_pattern_simulator.main()

    metadata_path = tmp_path / "metadata" / "fan_morse_simulation.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    rpm_path = tmp_path / "rpm" / "fan_rpm_timeline.csv"
    audio_path = tmp_path / "audio" / "fan_morse_synthetic.wav"
    rows = rpm_path.read_text(encoding="utf-8").splitlines()
    valid, errors = validate_metadata(metadata)

    assert metadata["source_type"] == SOURCE_TYPE_SYNTHETIC_SIMULATION
    assert metadata["capture_status"] == "COMPLETED"
    assert metadata["simulation_parameters"]["expected_morse"] == "... --- ..."
    assert metadata["simulation_parameters"]["physical_fan_control"] is False
    assert metadata["morse_detection"]["decoded_morse"] == "... --- ..."
    assert metadata["morse_detection"]["source_type"] == SOURCE_TYPE_SYNTHETIC_SIMULATION
    assert 0.0 <= metadata["morse_detection"]["match_score"] <= 1.0
    assert metadata["data_sha256"] == compute_file_sha256(str(rpm_path))
    assert metadata["synthetic_audio_sha256"] == compute_file_sha256(str(audio_path))
    assert len(rows) == metadata["sample_count"] + 1
    assert valid, errors


def test_fan_simulator_rejects_invalid_timeline_step():
    with pytest.raises(ValueError, match="step"):
        FanPatternSimulator().generate_timeline("SOS", time_step_sec=0)


def test_synthetic_fan_audio_is_detected_as_synthetic_sos():
    morse_config = MorseConfig()
    audio = SyntheticFanAudioGenerator(morse_config).generate_synthetic_audio("SOS")
    acoustic_config = AcousticConfig(sample_rate_hz=44100, chunk_size=2048)
    processor = AcousticProcessor(acoustic_config)
    detector = RealtimeMorseDetector(morse_config)
    events = []

    for chunk_id, start in enumerate(range(0, len(audio.audio) - 2048 + 1, 2048), start=1):
        chunk = AudioChunk(
            samples=audio.audio[start:start + 2048],
            timestamp=1000.0 + start / 44100,
            sample_rate_hz=44100,
            channels=1,
            is_synthetic=True,
            chunk_id=chunk_id,
        )
        event = detector.process_chunk(processor.process_chunk(chunk))
        if event is not None:
            events.append(event)

    assert events
    assert events[0].decoded_morse == "... --- ..."
    assert events[0].source == "SYNTHETIC TEST"
    assert events[0].match_score == pytest.approx(0.89)
