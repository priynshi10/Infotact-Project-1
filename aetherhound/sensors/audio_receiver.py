"""
Acoustic and Ultrasonic Microphone Array Sensor Module.
Provides low-latency audio capture for detecting CPU fan PWM speed variations,
disk acoustic harmonics, and ultrasonic covert channels.
"""

import time
import numpy as np
from typing import Dict, Any, Optional
from aetherhound.sensors.base import SignalSource
from aetherhound.config import AcousticSensorConfig

class AudioReceiver(SignalSource):
    """
    Multichannel Audio/Ultrasonic Ingestion Interface.
    Interfaces with physical USB microphone arrays / soundcards or
    falls back cleanly to real-time synthetic stream.
    """

    def __init__(self, config: Optional[AcousticSensorConfig] = None):
        cfg = config or AcousticSensorConfig()
        super().__init__(name="AcousticMicrophoneArray", sample_rate=cfg.sample_rate)
        self.config = cfg
        self.channels = cfg.channels
        self._stream = None
        self._hardware_active = False
        self._time_offset = 0.0

    def start(self) -> None:
        """Initialize audio hardware stream or virtual capture."""
        self.is_running = True
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            self._stream = p.open(
                format=pyaudio.paFloat32,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.config.chunk_size
            )
            self._hardware_active = True
        except Exception:
            # Physical audio capture device not present or unsupported; use high-fidelity software generation
            self._hardware_active = False

    def stop(self) -> None:
        """Close audio capture."""
        self.is_running = False
        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self._hardware_active = False

    def read_chunk(self, chunk_size: Optional[int] = None) -> np.ndarray:
        """
        Read multichannel acoustic samples.
        Returns: np.ndarray of shape (channels, chunk_size)
        """
        size = chunk_size or self.config.chunk_size
        if self._hardware_active and self._stream is not None:
            try:
                raw_data = self._stream.read(size, exception_on_overflow=False)
                data = np.frombuffer(raw_data, dtype=np.float32)
                return data.reshape((self.channels, size))
            except Exception:
                pass

        # High-fidelity baseline server room acoustic hum generator
        t = np.linspace(self._time_offset, self._time_offset + (size / self.sample_rate), size, endpoint=False)
        self._time_offset += (size / self.sample_rate)

        # Baseline: Multiple server fans rotating at ~2400 RPM (40 Hz fundamental, harmonics at 280Hz, 560Hz, 840Hz, 1120Hz)
        fan_harmonics = (
            0.15 * np.sin(2 * np.pi * 280 * t) +
            0.10 * np.sin(2 * np.pi * 560 * t) +
            0.08 * np.sin(2 * np.pi * 840 * t) +
            0.05 * np.sin(2 * np.pi * 1120 * t)
        )
        # Server room HVAC pink/white ambient floor
        thermal_noise = np.random.normal(0, 0.02, size)
        primary_ch = fan_harmonics + thermal_noise

        # Generate multichannel array with realistic microsecond propagation delays
        multichannel = np.zeros((self.channels, size), dtype=np.float32)
        for ch in range(self.channels):
            # Phase shift / spatial delay across microphone array elements
            delay_samples = ch * 2
            delayed = np.roll(primary_ch, delay_samples)
            # Add element-specific uncorrelated thermal noise
            multichannel[ch] = delayed + np.random.normal(0, 0.005, size).astype(np.float32)

        return multichannel

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "source_type": "Acoustic / Ultrasonic Array",
            "channels": self.channels,
            "sample_rate": self.sample_rate,
            "hardware_attached": self._hardware_active,
            "status": "RUNNING" if self.is_running else "STOPPED"
        }
