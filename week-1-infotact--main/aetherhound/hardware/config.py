"""
AetherHound Hardware Configuration Module
Defines configuration structures, hardware limits, validation routines,
and environment overrides for both RF (RTL-SDR) and Acoustic hardware.
"""

from dataclasses import dataclass, field
import os
from typing import Optional, Union


# RTL-SDR hardware specifications & safe limits
RTL_MIN_FREQ_HZ = 24_000_000       # 24 MHz
RTL_MAX_FREQ_HZ = 1_766_000_000    # 1.766 GHz
RTL_MIN_SAMPLE_RATE = 225_000      # 225 kHz
RTL_MAX_SAMPLE_RATE = 3_200_000    # 3.2 MHz (stable <= 2.4 MHz)
RTL_STABLE_SAMPLE_RATE = 2_048_000 # 2.048 MHz standard

# Standard audio rates
STANDARD_AUDIO_RATES = [16000, 22050, 44100, 48000, 96000, 192000]


@dataclass
class RFConfig:
    """Configuration parameters for RTL-SDR RF acquisition."""
    center_freq_hz: float = float(os.getenv("AETHERHOUND_RF_CENTER_FREQ_HZ", 433_920_000))  # 433.92 MHz ISM
    sample_rate_hz: float = float(os.getenv("AETHERHOUND_RF_SAMPLE_RATE_HZ", 2_048_000))
    gain: Union[str, float] = os.getenv("AETHERHOUND_RF_GAIN", "auto")
    ppm_correction: int = int(os.getenv("AETHERHOUND_RF_PPM_CORRECTION", 0))
    device_index: int = int(os.getenv("AETHERHOUND_RF_DEVICE_INDEX", 0))
    fft_size: int = int(os.getenv("AETHERHOUND_RF_FFT_SIZE", 2048))
    samples_per_window: int = int(os.getenv("AETHERHOUND_RF_WINDOW_SAMPLES", 16384))
    detection_threshold_sigma: float = float(os.getenv("AETHERHOUND_RF_SIGMA_THRESHOLD", 4.5))
    rolling_baseline_len: int = 50

    def validate(self) -> None:
        """Validate RF configuration against hardware-supported constraints."""
        if not (RTL_MIN_FREQ_HZ <= self.center_freq_hz <= RTL_MAX_FREQ_HZ):
            raise ValueError(
                f"Center frequency {self.center_freq_hz / 1e6:.2f} MHz is outside RTL-SDR range "
                f"({RTL_MIN_FREQ_HZ / 1e6:.1f} MHz - {RTL_MAX_FREQ_HZ / 1e6:.1f} MHz)"
            )
        if not (RTL_MIN_SAMPLE_RATE <= self.sample_rate_hz <= RTL_MAX_SAMPLE_RATE):
            raise ValueError(
                f"Sample rate {self.sample_rate_hz / 1e3:.1f} kHz is outside stable range "
                f"({RTL_MIN_SAMPLE_RATE / 1e3:.0f} kHz - {RTL_MAX_SAMPLE_RATE / 1e3:.0f} kHz)"
            )
        if isinstance(self.gain, str) and self.gain.lower() != "auto":
            try:
                self.gain = float(self.gain)
            except ValueError:
                raise ValueError(f"Invalid gain specification: '{self.gain}'. Must be 'auto' or a numeric dB value.")
        if self.fft_size < 128 or (self.fft_size & (self.fft_size - 1)) != 0:
            raise ValueError(f"FFT size {self.fft_size} must be a power of 2 and >= 128")
        if self.samples_per_window < self.fft_size:
            raise ValueError(f"Samples per window ({self.samples_per_window}) must be >= FFT size ({self.fft_size})")


@dataclass
class AcousticConfig:
    """Configuration parameters for PyAudio acoustic acquisition."""
    sample_rate_hz: int = int(os.getenv("AETHERHOUND_AUDIO_SAMPLE_RATE_HZ", 44100))
    channels: int = int(os.getenv("AETHERHOUND_AUDIO_CHANNELS", 1))
    device_index: Optional[int] = None if os.getenv("AETHERHOUND_AUDIO_DEVICE_INDEX", "-1") == "-1" else int(os.getenv("AETHERHOUND_AUDIO_DEVICE_INDEX", "-1"))
    chunk_size: int = int(os.getenv("AETHERHOUND_AUDIO_CHUNK_SIZE", 2048))
    audio_format: str = "float32"  # float32 or int16
    energy_threshold_factor: float = float(os.getenv("AETHERHOUND_ACOUSTIC_ENERGY_THRESHOLD", 3.0))
    rolling_baseline_len: int = 50

    def validate(self) -> None:
        """Validate acoustic parameters against sound hardware standards."""
        if self.sample_rate_hz not in STANDARD_AUDIO_RATES:
            # Allow custom rates with warning
            if self.sample_rate_hz < 8000 or self.sample_rate_hz > 384000:
                raise ValueError(f"Sample rate {self.sample_rate_hz} Hz is not supported by standard audio hardware")
        if self.channels not in (1, 2):
            raise ValueError(f"Unsupported channel count {self.channels}. AetherHound supports mono (1) or stereo (2).")
        if self.chunk_size < 256 or (self.chunk_size & (self.chunk_size - 1)) != 0:
            raise ValueError(f"Chunk size {self.chunk_size} should be a power of 2 and >= 256")


@dataclass
class MorseConfig:
    """Configuration for benign fan Morse-code pattern simulation and recognition."""
    dot_duration_sec: float = float(os.getenv("AETHERHOUND_MORSE_DOT_DURATION_SEC", 0.20))
    dash_duration_sec: float = float(os.getenv("AETHERHOUND_MORSE_DASH_DURATION_SEC", 0.60))
    element_gap_sec: Optional[float] = None
    letter_gap_sec: Optional[float] = None
    word_gap_sec: Optional[float] = None
    timing_tolerance: float = float(os.getenv("AETHERHOUND_MORSE_TIMING_TOLERANCE", 0.40))
    base_rpm: float = float(os.getenv("AETHERHOUND_FAN_BASE_RPM", 1200))
    low_rpm: float = float(os.getenv("AETHERHOUND_FAN_LOW_RPM", 900))
    high_rpm: float = float(os.getenv("AETHERHOUND_FAN_HIGH_RPM", 1800))

    def __post_init__(self) -> None:
        if self.element_gap_sec is None:
            self.element_gap_sec = self.dot_duration_sec
        if self.letter_gap_sec is None:
            self.letter_gap_sec = 3.0 * self.dot_duration_sec
        if self.word_gap_sec is None:
            self.word_gap_sec = 7.0 * self.dot_duration_sec

    def validate(self) -> None:
        if self.dot_duration_sec <= 0:
            raise ValueError("Dot duration must be positive")
        if self.dash_duration_sec <= self.dot_duration_sec:
            raise ValueError("Dash duration must be longer than dot duration")
        if not (0.05 <= self.timing_tolerance <= 0.70):
            raise ValueError("Timing tolerance should be between 0.05 (5%) and 0.70 (70%)")


@dataclass
class HardwareConfig:
    """Master hardware configuration uniting RF, Acoustic, and Simulator configs."""
    rf: RFConfig = field(default_factory=RFConfig)
    acoustic: AcousticConfig = field(default_factory=AcousticConfig)
    morse: MorseConfig = field(default_factory=MorseConfig)

    def validate_all(self) -> None:
        self.rf.validate()
        self.acoustic.validate()
        self.morse.validate()
