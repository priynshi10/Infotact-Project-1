"""
Unit tests for Real-Time Streaming Morse Pattern Recognition.
"""

import numpy as np
import pytest

from aetherhound.detection.morse_detector import RealtimeMorseDetector
from aetherhound.dsp.acoustic_processor import AcousticProcessor
from aetherhound.hardware.acoustic_capture import AudioChunk
from aetherhound.hardware.config import AcousticConfig, MorseConfig
from aetherhound.mock_malware.audio_generator import SyntheticFanAudioGenerator


def test_sos_sequence_recognition():
    """Verify that a synthesized SOS audio stream is recognized in real time."""
    morse_cfg = MorseConfig(dot_duration_sec=0.10, dash_duration_sec=0.30)
    ac_cfg = AcousticConfig(sample_rate_hz=16000, chunk_size=1024)

    generator = SyntheticFanAudioGenerator(morse_cfg, sample_rate_hz=16000)
    res = generator.generate_synthetic_audio(message="SOS", lead_in_sec=0.3, lead_out_sec=0.3)

    acoustic_proc = AcousticProcessor(ac_cfg)
    detector = RealtimeMorseDetector(morse_cfg, target_message="SOS")

    chunk_size = ac_cfg.chunk_size
    sr = ac_cfg.sample_rate_hz
    num_chunks = len(res.audio) // chunk_size

    detected_event = None
    start_t = 100.0

    for i in range(num_chunks):
        slice_samples = res.audio[i * chunk_size : (i + 1) * chunk_size]
        chunk = AudioChunk(
            samples=slice_samples,
            timestamp=start_t + (i * chunk_size / sr),
            sample_rate_hz=sr,
            channels=1,
            is_synthetic=True,
            chunk_id=i + 1,
        )

        proc_chunk = acoustic_proc.process_chunk(chunk)
        event = detector.process_chunk(proc_chunk)
        if event:
            detected_event = event

    assert detected_event is not None
    assert detected_event.target_pattern == "SOS"
    assert detected_event.decoded_morse == "... --- ..."
    assert detected_event.match_score >= 0.70
    assert detected_event.source == "SYNTHETIC TEST"


def test_incorrect_sequence_rejection():
    """Verify that an arbitrary sequence (e.g. 'EEE' or ambient noise) is NOT recognized as SOS."""
    morse_cfg = MorseConfig(dot_duration_sec=0.10, dash_duration_sec=0.30)
    ac_cfg = AcousticConfig(sample_rate_hz=16000, chunk_size=1024)

    # Generate 'EEE' -> ... only, not SOS
    generator = SyntheticFanAudioGenerator(morse_cfg, sample_rate_hz=16000)
    res = generator.generate_synthetic_audio(message="E E E", lead_in_sec=0.2, lead_out_sec=0.2)

    acoustic_proc = AcousticProcessor(ac_cfg)
    detector = RealtimeMorseDetector(morse_cfg, target_message="SOS")

    chunk_size = ac_cfg.chunk_size
    sr = ac_cfg.sample_rate_hz
    num_chunks = len(res.audio) // chunk_size

    detected_event = None
    start_t = 200.0

    for i in range(num_chunks):
        slice_samples = res.audio[i * chunk_size : (i + 1) * chunk_size]
        chunk = AudioChunk(
            samples=slice_samples,
            timestamp=start_t + (i * chunk_size / sr),
            sample_rate_hz=sr,
            channels=1,
            is_synthetic=True,
            chunk_id=i + 1,
        )

        proc_chunk = acoustic_proc.process_chunk(chunk)
        event = detector.process_chunk(proc_chunk)
        if event:
            detected_event = event

    # 'EEE' must never trigger SOS detection
    assert detected_event is None
