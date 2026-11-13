"""
Abstract Base Classes for AetherHound Sensor Ingestion.
Defines interfaces for Acoustic and RF signal sources.
"""

from abc import ABC, abstractmethod
from typing import Generator, Dict, Any, Optional
import numpy as np

class SignalSource(ABC):
    """Abstract Base Class for all physical and simulated signal sources."""

    def __init__(self, name: str, sample_rate: int):
        self.name = name
        self.sample_rate = sample_rate
        self.is_running = False

    @abstractmethod
    def start(self) -> None:
        """Initialize and start the sensor stream."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the sensor stream and release hardware handles."""
        pass

    @abstractmethod
    def read_chunk(self, chunk_size: int) -> np.ndarray:
        """
        Read a single block of raw sensor samples.
        For audio: Real array of shape (channels, chunk_size) or (chunk_size,).
        For SDR: Complex64 array of shape (chunk_size,).
        """
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return operational parameters (gain, center frequency, sample rate, etc.)."""
        pass
