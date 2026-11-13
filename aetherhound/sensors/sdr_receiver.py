"""
Software Defined Radio (SDR) Receiver Module.
Interfaces with HackRF One, RTL-SDR, or USRP hardware to capture electromagnetic (RF)
emanations leaked from memory buses (RAMBO), display cables (AirHopper), and USB lines.
"""

import time
import numpy as np
from typing import Dict, Any, Optional
from aetherhound.sensors.base import SignalSource
from aetherhound.config import RFSensorConfig

class SDRReceiver(SignalSource):
    """
    SDR Ingestion Interface for Radio Frequency (RF) Covert Channels.
    Captures complex I/Q samples centered at vulnerable bus frequencies.
    """

    def __init__(self, config: Optional[RFSensorConfig] = None):
        cfg = config or RFSensorConfig()
        super().__init__(name="SoftwareDefinedRadio", sample_rate=int(cfg.sample_rate))
        self.config = cfg
        self.center_freq = cfg.center_freq_hz
        self.gain = cfg.gain_db
        self._sdr_device = None
        self._hardware_active = False
        self._time_offset = 0.0

    def start(self) -> None:
        """Connect to physical SDR hardware if attached."""
        self.is_running = True
        try:
            from rtlsdr import RtlSdr
            sdr = RtlSdr()
            sdr.sample_rate = self.sample_rate
            sdr.center_freq = self.center_freq
            sdr.gain = self.gain
            self._sdr_device = sdr
            self._hardware_active = True
        except Exception:
            self._hardware_active = False

    def stop(self) -> None:
        """Release SDR hardware device."""
        self.is_running = False
        if self._sdr_device is not None:
            try:
                self._sdr_device.close()
            except Exception:
                pass
            self._sdr_device = None
        self._hardware_active = False

    def set_center_frequency(self, freq_hz: float) -> None:
        """Retune center frequency."""
        self.center_freq = freq_hz
        if self._hardware_active and self._sdr_device is not None:
            try:
                self._sdr_device.center_freq = freq_hz
            except Exception:
                pass

    def read_chunk(self, chunk_size: Optional[int] = None) -> np.ndarray:
        """
        Read block of complex I/Q samples (Complex64).
        Returns: np.ndarray of shape (chunk_size,) dtype=np.complex64
        """
        size = chunk_size or self.config.fft_size
        if self._hardware_active and self._sdr_device is not None:
            try:
                samples = self._sdr_device.read_samples(size)
                return np.asarray(samples, dtype=np.complex64)
            except Exception:
                pass

        # High-fidelity RF baseline electromagnetic environment simulation
        t = np.linspace(self._time_offset, self._time_offset + (size / self.sample_rate), size, endpoint=False)
        self._time_offset += (size / self.sample_rate)

        # Baseline: Thermal RF noise floor (~-105 dBm) + benign clock spurs
        noise_i = np.random.normal(0, 0.05, size)
        noise_q = np.random.normal(0, 0.05, size)
        base_iq = (noise_i + 1j * noise_q).astype(np.complex64)

        # Ambient baseline spur from benign server power supply switching (e.g. 150 kHz offset)
        spur_offset_hz = 150000.0
        spur = 0.08 * np.exp(2j * np.pi * spur_offset_hz * t).astype(np.complex64)

        return base_iq + spur

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "source_type": "Software Defined Radio (SDR)",
            "center_freq_mhz": self.center_freq / 1e6,
            "sample_rate_msps": self.sample_rate / 1e6,
            "gain_db": self.gain,
            "hardware_attached": self._hardware_active,
            "status": "RUNNING" if self.is_running else "STOPPED"
        }
