"""
AetherHound Real-Time SOS Morse Pattern Detector Module
Continuously analyzes incoming microphone audio chunks in real time,
extracts envelope, tracks pulse onsets and offsets, classifies dot/dash durations,
reconstructs Morse symbols, and detects target patterns (e.g. 'SOS') with confidence scoring.
"""

from collections import deque
from dataclasses import dataclass, field
import time
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np

from aetherhound.dsp.acoustic_processor import AcousticProcessedChunk
from aetherhound.hardware.config import MorseConfig


@dataclass
class MorsePulse:
    """A detected acoustic pulse interval."""
    is_active: bool            # True for pulse, False for gap
    start_time: float          # POSIX timestamp of onset
    end_time: float            # POSIX timestamp of offset
    duration_sec: float        # Duration in seconds
    mean_amplitude: float      # Average envelope amplitude during pulse
    classified_symbol: str     # '.', '-', 'gap_elem', 'gap_letter', 'gap_word', 'noise'


@dataclass
class MorsePatternEvent:
    """Structured Morse Pattern Detection Event."""
    event_type: str                   # "Covert Acoustic Morse Channel Detected"
    sensor_id: str                    # "MIC-01"
    target_pattern: str               # "SOS"
    decoded_morse: str                # "... --- ..."
    detection_method: str             # "Acoustic Pulse Timing"
    match_score: float                # Confidence score [0.0 - 1.0]
    timestamp: float                  # Detection timestamp
    source: str                       # "LIVE MICROPHONE" or "SYNTHETIC TEST"
    result: str                       # "PATTERN RECOGNIZED" or "PATTERN GENERATED"
    evidence: Dict[str, float] = field(default_factory=dict)


class RealtimeMorseDetector:
    """
    Streaming real-time Morse code detector.
    Analyzes live audio chunks frame-by-frame as acquired by the microphone.
    """

    def __init__(
        self,
        config: Optional[MorseConfig] = None,
        sensor_id: str = "MIC-01",
        target_message: str = "SOS",
    ):
        self.config = config or MorseConfig()
        self.config.validate()
        self.sensor_id = sensor_id
        self.target_message = target_message

        # State machine variables for pulse edge tracking
        self._current_state_is_pulse: bool = False
        self._state_start_time: float = 0.0
        self._state_envelope_samples: List[float] = []

        # Rolling buffer of classified pulses and symbols
        self._recent_pulses: Deque[MorsePulse] = deque(maxlen=30)
        self._classified_symbols: Deque[Tuple[str, float, float]] = deque(maxlen=20)  # (symbol, duration, timestamp)

        # Baseline envelope tracking
        self._ambient_envelope_history: Deque[float] = deque(maxlen=100)
        self._recent_env_samples: Deque[float] = deque(maxlen=2000)
        self._last_detection_time: float = 0.0
        self._detection_cooldown_sec: float = 2.0

        # Last detected event
        self._last_event: Optional[MorsePatternEvent] = None

    @property
    def last_event(self) -> Optional[MorsePatternEvent]:
        return self._last_event

    def reset(self) -> None:
        """Reset internal detector state."""
        self._current_state_is_pulse = False
        self._state_start_time = 0.0
        self._state_envelope_samples.clear()
        self._recent_pulses.clear()
        self._classified_symbols.clear()
        self._recent_env_samples.clear()
        self._last_event = None

    def process_chunk(self, chunk: AcousticProcessedChunk) -> Optional[MorsePatternEvent]:
        """
        Process a live audio chunk in real time and evaluate for SOS pattern.
        """
        envelope = chunk.envelope
        now = chunk.timestamp
        sr = chunk.sample_rate_hz
        chunk_duration = len(envelope) / sr

        # Decimate envelope and append to rolling historical sample buffer
        dec = envelope[::32]
        self._recent_env_samples.extend(dec)

        p15 = float(np.percentile(self._recent_env_samples, 15))
        p85 = float(np.percentile(self._recent_env_samples, 85))

        # Dynamic adaptive Schmitt trigger thresholds with hysteresis to eliminate flutter
        dyn_range = p85 - p15
        if dyn_range >= 0.018:
            th_high = p15 + 0.54 * dyn_range
            th_low = p15 + 0.36 * dyn_range
        else:
            th_high = max(0.020, p15 * 1.6)
            th_low = max(0.015, p15 * 1.2)

        # Iterate over sub-samples in chunk to find edge transitions
        # Subdivide chunk into ~10ms evaluation blocks for responsive edge detection
        block_size = max(1, int(sr * 0.010))
        num_blocks = len(envelope) // block_size

        detected_event: Optional[MorsePatternEvent] = None

        for b in range(num_blocks):
            sub_env = envelope[b * block_size : (b + 1) * block_size]
            mean_block_amp = float(np.mean(sub_env))
            block_time = now + (b * block_size / sr)

            if not self._current_state_is_pulse:
                is_pulse = mean_block_amp >= th_high
            else:
                is_pulse = mean_block_amp > th_low

            if self._state_start_time == 0.0:
                self._current_state_is_pulse = is_pulse
                self._state_start_time = block_time
                self._state_envelope_samples = [mean_block_amp]
                continue

            if is_pulse == self._current_state_is_pulse:
                self._state_envelope_samples.append(mean_block_amp)
            else:
                # Edge transition detected! Finalize previous interval
                interval_duration = block_time - self._state_start_time
                mean_amp = float(np.mean(self._state_envelope_samples)) if self._state_envelope_samples else mean_block_amp

                # Minimum pulse duration filter to ignore micro glitches (< 45% of dot duration)
                min_pulse_dur = max(0.025, self.config.dot_duration_sec * 0.45)
                min_gap_dur = max(0.025, self.config.dot_duration_sec * 0.35)

                if (self._current_state_is_pulse and interval_duration >= min_pulse_dur) or (not self._current_state_is_pulse and interval_duration >= min_gap_dur):
                    symbol = self._classify_interval(
                        is_active=self._current_state_is_pulse,
                        duration_sec=interval_duration,
                    )

                    pulse = MorsePulse(
                        is_active=self._current_state_is_pulse,
                        start_time=self._state_start_time,
                        end_time=block_time,
                        duration_sec=interval_duration,
                        mean_amplitude=mean_amp,
                        classified_symbol=symbol,
                    )
                    self._recent_pulses.append(pulse)

                    if self._current_state_is_pulse and symbol in (".", "-"):
                        self._classified_symbols.append((symbol, interval_duration, block_time))
                        # Check pattern immediately on new symbol
                        event = self._evaluate_pattern(chunk.is_synthetic, block_time)
                        if event:
                            detected_event = event

                # Transition to new state
                self._current_state_is_pulse = is_pulse
                self._state_start_time = block_time
                self._state_envelope_samples = [mean_block_amp]

        return detected_event

    def _classify_interval(self, is_active: bool, duration_sec: float) -> str:
        """Classify a pulse or gap duration into Morse dot, dash, or spacing."""
        dot = self.config.dot_duration_sec
        dash = self.config.dash_duration_sec
        tol = self.config.timing_tolerance

        if is_active:
            # Active pulse: split threshold midway between dot and dash
            split_thresh = (dot + dash) / 2.0
            if duration_sec <= split_thresh:
                return "."
            else:
                return "-"
        else:
            # Idle gap between pulses
            elem_gap = self.config.element_gap_sec or dot
            char_gap = self.config.letter_gap_sec or (3.0 * dot)
            word_gap = self.config.word_gap_sec or (7.0 * dot)

            if duration_sec <= (elem_gap + char_gap) / 2.0:
                return "gap_elem"
            elif duration_sec <= (char_gap + word_gap) / 2.0:
                return "gap_letter"
            else:
                return "gap_word"

    def _evaluate_pattern(self, is_synthetic: bool, current_time: float) -> Optional[MorsePatternEvent]:
        """
        Check if recent symbols match the target sequence ('SOS' -> 3 dots, 3 dashes, 3 dots).
        Calculates exact mathematical match score based on timing error and energy contrast.
        """
        if (current_time - self._last_detection_time) < self._detection_cooldown_sec:
            return None

        # Target sequence symbols for SOS: ['.', '.', '.', '-', '-', '-', '.', '.', '.']
        expected_symbols = [".", ".", ".", "-", "-", "-", ".", ".", "."]
        target_len = len(expected_symbols)

        if len(self._classified_symbols) < target_len:
            return None

        # Take last 9 symbols
        symbols_tail = list(self._classified_symbols)[-target_len:]
        actual_symbols = [s[0] for s in symbols_tail]
        actual_durations = [s[1] for s in symbols_tail]

        if actual_symbols != expected_symbols:
            return None

        # Match confirmed! Compute detailed confidence match score:
        # 1. Timing error metric:
        # Sum of normalized timing errors across all 9 symbols:
        # error_i = |actual - expected| / expected
        timing_errors = []
        for sym, dur in zip(actual_symbols, actual_durations):
            expected_dur = self.config.dot_duration_sec if sym == "." else self.config.dash_duration_sec
            norm_err = min(1.0, abs(dur - expected_dur) / expected_dur)
            timing_errors.append(norm_err)

        mean_timing_err = float(np.mean(timing_errors))
        timing_accuracy_score = max(0.0, 1.0 - mean_timing_err)

        # 2. Sequence consistency score: 100% since symbols matched exactly
        symbol_match_score = 1.0

        # Overall composite match score:
        # 70% timing accuracy + 30% symbol fidelity
        match_score = round(0.70 * timing_accuracy_score + 0.30 * symbol_match_score, 3)

        self._last_detection_time = current_time

        source_label = "SYNTHETIC TEST" if is_synthetic else "LIVE MICROPHONE"
        result_label = "PATTERN GENERATED" if is_synthetic else "PATTERN RECOGNIZED"

        event = MorsePatternEvent(
            event_type="Covert Acoustic Morse Channel Detected",
            sensor_id=self.sensor_id,
            target_pattern=self.target_message,
            decoded_morse="... --- ...",
            detection_method="Acoustic Pulse Timing",
            match_score=match_score,
            timestamp=current_time,
            source=source_label,
            result=result_label,
            evidence={
                "mean_timing_error_pct": round(mean_timing_err * 100, 1),
                "timing_accuracy": round(timing_accuracy_score, 3),
                "symbol_count": 9,
                "dot_ref_sec": self.config.dot_duration_sec,
                "dash_ref_sec": self.config.dash_duration_sec,
            },
        )
        self._last_event = event
        return event
