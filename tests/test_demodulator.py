"""
Unit Tests for Covert Channel Signal Demodulation.
"""

import pytest
from aetherhound.engine.demodulator import CovertChannelDemodulator

def test_morse_encoding_and_decoding():
    demod = CovertChannelDemodulator()
    text = "DEFENSE"
    encoded = demod.encode_to_morse(text)
    decoded = demod.decode_morse(encoded)
    assert decoded == text

def test_binary_stream_decoding():
    demod = CovertChannelDemodulator()
    # 'A' is 65 = 01000001
    bits = [0, 1, 0, 0, 0, 0, 0, 1]
    decoded = demod.decode_binary_stream(bits)
    assert decoded == "A"
