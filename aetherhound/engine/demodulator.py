"""
Covert Channel Demodulator & Signal Decoder.
Reconstructs exfiltrated confidential payloads (Morse Code, OOK, FSK)
from intercepted acoustic fan pulses or memory bus RF emanations.
"""

import time
import numpy as np
from typing import List, Dict, Optional, Tuple

class CovertChannelDemodulator:
    """
    SIGINT demodulator for Fansmitter and RAMBO covert protocols.
    Decodes pulse-width patterns and frequency shifts back to plaintext.
    """

    MORSE_CODE_DICT = {
        '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E',
        '..-.': 'F', '--.': 'G', '....': 'H', '..': 'I', '.---': 'J',
        '-.-': 'K', '.-..': 'L', '--': 'M', '-.': 'N', '---': 'O',
        '.--.': 'P', '--.-': 'Q', '.-.': 'R', '...': 'S', '-': 'T',
        '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X', '-.--': 'Y',
        '--..': 'Z', '-----': '0', '.----': '1', '..---': '2', '...--': '3',
        '....-': '4', '.....': '5', '-....': '6', '--...': '7', '---..': '8',
        '----.': '9', '.-.-.-': '.', '--..--': ',', '..--..': '?', '-..-.': '/',
        '-....-': '-', '---...': ':', '-.-.--': '!'
    }

    def __init__(self):
        self._rev_morse = {v: k for k, v in self.MORSE_CODE_DICT.items()}
        self._pulse_history: List[Tuple[float, bool]] = []
        self._accumulated_symbols: List[str] = []

    def encode_to_morse(self, plaintext: str) -> str:
        """Helper to encode a string into Morse code representation."""
        words = plaintext.upper().split(' ')
        morse_words = []
        for word in words:
            morse_chars = [self._rev_morse[c] for c in word if c in self._rev_morse]
            morse_words.append(' '.join(morse_chars))
        return ' / '.join(morse_words)

    def decode_morse(self, morse_string: str) -> str:
        """Decode a sequence of Morse code tokens (e.g. '... --- ...')."""
        words = morse_string.strip().split(' / ')
        decoded_words = []
        for word in words:
            chars = word.split(' ')
            decoded_chars = [self.MORSE_CODE_DICT.get(c, '') for c in chars if c]
            decoded_words.append(''.join(decoded_chars))
        return ' '.join(decoded_words)

    def process_pulse(self, is_carrier_present: bool, duration_sec: float) -> Optional[str]:
        """
        Stream decoder: Ingests carrier-present boolean and pulse durations.
        Translates dot (short), dash (long), and letter/word spaces into ASCII characters.
        """
        # Nominal unit time: dot = ~0.2s, dash = ~0.6s
        if not is_carrier_present:
            # Space between pulses or characters
            if duration_sec > 1.2 and self._accumulated_symbols:
                token = ''.join(self._accumulated_symbols)
                self._accumulated_symbols.clear()
                return self.MORSE_CODE_DICT.get(token, '?')
        else:
            if duration_sec < 0.4:
                self._accumulated_symbols.append('.')
            else:
                self._accumulated_symbols.append('-')
        return None

    def decode_binary_stream(self, bits: List[int]) -> str:
        """Decode a stream of 8-bit binary integers into ASCII text."""
        chars = []
        for i in range(0, len(bits) - 7, 8):
            byte_bits = bits[i:i+8]
            val = int(''.join(str(b) for b in byte_bits), 2)
            if 32 <= val <= 126:  # Printable ASCII
                chars.append(chr(val))
        return ''.join(chars)
