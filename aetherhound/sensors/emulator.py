"""
High-Fidelity Server Room Environment & Covert Channel Emulator.
Generates comprehensive synthetic RF & Acoustic signals:
- Baseline server rack acoustic hum (multiple blades, fan speed variations)
- Baseline RF electromagnetic emissions (switching power supplies, clock leakage)
- Injected Covert Channels:
  * Fansmitter: Acoustic PWM modulation with Morse code or binary FSK
  * RAMBO: Memory-bus RF burst modulation
- Environmental transients (door closing, speech, air conditioning surges)
- Realistic multi-sensor array delays and inverse-square/log-distance path loss.
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from aetherhound.config import AetherHoundConfig, DEFAULT_CONFIG

class AirGapEnvironmentEmulator:
    """
    Physical-layer air-gapped server room acoustic and RF emulator.
    Supports injecting malware exfiltration on-the-fly and calculating
    multi-sensor spatial signals for precise rack triangulation.
    """

    def __init__(self, config: Optional[AetherHoundConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self.acoustic_sr = self.config.acoustic.sample_rate
        self.rf_sr = int(self.config.rf.sample_rate)
        self.time_acoustic = 0.0
        self.time_rf = 0.0

        # Covert channel injection state
        self.fansmitter_active = False
        self.fansmitter_rack = "Rack-Delta"
        self.fansmitter_freq = 1950.0  # Anomaly tone (Hz)
        self.fansmitter_state = 0  # 0: Off, 1: On (pulse)
        self.fansmitter_pattern = []  # list of durations or symbols

        self.rambo_active = False
        self.rambo_rack = "Rack-Beta"
        self.rambo_offset_hz = 75000.0  # 75 kHz offset from RF center
        self.rambo_state = 0

        # Speed of sound in air (m/s)
        self.speed_of_sound = 343.0

    def set_fansmitter_state(self, active: bool, rack: str = "Rack-Delta", freq_hz: float = 1950.0) -> None:
        """Toggle CPU Fan acoustic exfiltration attack."""
        self.fansmitter_active = active
        self.fansmitter_rack = rack
        self.fansmitter_freq = freq_hz

    def set_rambo_state(self, active: bool, rack: str = "Rack-Beta", offset_hz: float = 75000.0) -> None:
        """Toggle RAM bus RF electromagnetic exfiltration attack."""
        self.rambo_active = active
        self.rambo_rack = rack
        self.rambo_offset_hz = offset_hz

    def generate_multichannel_acoustic(self, chunk_size: int) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        Generate multichannel acoustic microphone array samples.
        Returns:
            multichannel_audio: np.ndarray (channels, chunk_size)
            rssi_per_sensor: Dict[str, float] measured power in dB SPL per sensor node
        """
        sr = self.acoustic_sr
        t = np.linspace(self.time_acoustic, self.time_acoustic + (chunk_size / sr), chunk_size, endpoint=False)
        self.time_acoustic += (chunk_size / sr)

        # 1. Baseline Server Room Hum (48-blade rack harmonics + HVAC pink noise)
        baseline_hum = (
            0.18 * np.sin(2 * np.pi * 320.0 * t) +
            0.14 * np.sin(2 * np.pi * 640.0 * t) +
            0.09 * np.sin(2 * np.pi * 960.0 * t) +
            0.06 * np.sin(2 * np.pi * 1280.0 * t) +
            0.04 * np.sin(2 * np.pi * 1600.0 * t)
        )
        # Random thermal airflow turbulence
        turbulence = np.random.normal(0, 0.025, chunk_size)
        ambient_signal = baseline_hum + turbulence

        sensors = list(self.config.layout.sensor_nodes.items())
        n_sensors = len(sensors)
        audio_array = np.zeros((n_sensors, chunk_size), dtype=np.float32)
        rssi_levels: Dict[str, float] = {}

        # 2. Add Covert Fansmitter Signal if active
        for i, (sensor_name, sensor_pos) in enumerate(sensors):
            ch_signal = ambient_signal.copy()

            if self.fansmitter_active:
                rack_pos = self.config.layout.racks.get(self.fansmitter_rack, (4.0, 5.0))
                # Calculate Euclidean distance from infected rack to sensor
                dist = np.sqrt((rack_pos[0] - sensor_pos[0])**2 + (rack_pos[1] - sensor_pos[1])**2)
                dist = max(dist, 0.5)  # Avoid div by zero

                # Time delay in samples
                delay_sec = dist / self.speed_of_sound
                delay_samples = int(delay_sec * sr)

                # Acoustic attenuation (Log-distance path loss)
                pl_exp = self.config.layout.path_loss_exponent
                attenuation = 1.0 / (dist ** (pl_exp / 2.0))

                # Fansmitter tone with slight frequency jitter (fan PWM instability)
                jitter = 5.0 * np.sin(2 * np.pi * 1.5 * t)
                tone = np.sin(2 * np.pi * (self.fansmitter_freq + jitter) * t)

                # Delay tone
                delayed_tone = np.roll(tone, delay_samples)
                covert_signal = (delayed_tone * attenuation * 0.45).astype(np.float32)

                ch_signal += covert_signal

            # Add sensor-specific thermal noise
            ch_signal += np.random.normal(0, 0.008, chunk_size).astype(np.float32)
            audio_array[i] = ch_signal

            # Calculate RMS power in dB
            rms = np.sqrt(np.mean(ch_signal**2) + 1e-12)
            db_spl = 20 * np.log10(rms) + 94.0  # Referenced to 20 uPa
            rssi_levels[sensor_name] = float(db_spl)

        return audio_array, rssi_levels

    def generate_rf_iq(self, chunk_size: int) -> np.ndarray:
        """
        Generate SDR complex I/Q samples.
        Returns: np.ndarray shape (chunk_size,) dtype=complex64
        """
        sr = self.rf_sr
        t = np.linspace(self.time_rf, self.time_rf + (chunk_size / sr), chunk_size, endpoint=False)
        self.time_rf += (chunk_size / sr)

        # Baseline: Complex Gaussian noise floor (~-100 dBm)
        noise = (np.random.normal(0, 0.04, chunk_size) + 1j * np.random.normal(0, 0.04, chunk_size)).astype(np.complex64)

        # Benign server switching transient
        base_spur = 0.06 * np.exp(2j * np.pi * 120000.0 * t).astype(np.complex64)
        rf_iq = noise + base_spur

        # RAMBO Covert Channel Injection (Memory-bus high-frequency burst)
        if self.rambo_active:
            # Narrowband RF carrier with square-wave modulation
            mod = 0.5 * (1.0 + np.sign(np.sin(2 * np.pi * 500.0 * t)))
            covert_rf = (0.28 * mod * np.exp(2j * np.pi * self.rambo_offset_hz * t)).astype(np.complex64)
            rf_iq += covert_rf

        return rf_iq
