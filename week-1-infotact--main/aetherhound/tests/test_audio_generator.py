"""
Unit tests for Synthetic Fan Audio Generator and Fan Pattern Simulator.
"""

import os
import numpy as np
import pytest
import soundfile as sf

from aetherhound.hardware.config import MorseConfig
from aetherhound.mock_malware.audio_generator import SyntheticFanAudioGenerator
from aetherhound.mock_malware.fan_pattern_simulator import FanPatternSimulator


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
