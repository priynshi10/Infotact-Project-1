"""
Unit tests for Morse Code Encoder and Timing Generator.
"""

import pytest
from aetherhound.hardware.config import MorseConfig
from aetherhound.mock_malware.morse_encoder import MorseEncoder, MorseInterval


def test_sos_text_encoding():
    encoder = MorseEncoder()
    encoded = encoder.text_to_morse("SOS")
    assert encoded == "... --- ..."


def test_other_character_encoding():
    encoder = MorseEncoder()
    assert encoder.text_to_morse("E") == "."
    assert encoder.text_to_morse("T") == "-"
    assert encoder.text_to_morse("A") == ".-"


def test_interval_structure():
    cfg = MorseConfig(dot_duration_sec=0.1, dash_duration_sec=0.3, element_gap_sec=0.1, letter_gap_sec=0.3)
    encoder = MorseEncoder(cfg)
    intervals = encoder.generate_intervals("SOS")

    # S: 3 dots (2 elem gaps) = 5
    # Letter gap = 1
    # O: 3 dashes (2 elem gaps) = 5
    # Letter gap = 1
    # S: 3 dots (2 elem gaps) = 5
    # Total = 17 intervals
    assert len(intervals) == 17

    active_intervals = [it for it in intervals if it.is_active]
    assert len(active_intervals) == 9  # 3 + 3 + 3 pulses
    symbols = [it.symbol for it in active_intervals]
    assert symbols == [".", ".", ".", "-", "-", "-", ".", ".", "."]


def test_timing_durations():
    cfg = MorseConfig(dot_duration_sec=0.2, dash_duration_sec=0.6)
    encoder = MorseEncoder(cfg)
    intervals = encoder.generate_intervals("E T")

    # E is '.', gap_word, T is '-'
    assert intervals[0].duration_sec == pytest.approx(0.2)
    assert intervals[0].symbol == "."
    assert intervals[-1].duration_sec == pytest.approx(0.6)
    assert intervals[-1].symbol == "-"
