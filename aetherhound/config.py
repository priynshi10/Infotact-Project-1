"""
AetherHound System Configuration Module
Contains global configurations for sensors, DSP, Autoencoder ML, Triangulation, and Alerting.
Designed for air-gapped hardware deployment on edge systems (e.g. Raspberry Pi / Jetson).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Dict
import os

@dataclass
class AcousticSensorConfig:
    """Acoustic & Ultrasonic Microphone Array Parameters."""
    sample_rate: int = 48000  # 48 kHz standard capture (supports up to 24 kHz Nyquist)
    ultrasonic_sample_rate: int = 96000  # 96 kHz for ultrasonic near-airgap channels
    channels: int = 4  # 4-element microphone array for spatial TDoA/RSSI
    chunk_size: int = 2048  # Samples per processing buffer
    baseline_fan_rpm_range: Tuple[int, int] = (1200, 3600)  # Standard server fan range
    covert_fan_fsk_freqs: Tuple[float, float] = (1800.0, 2400.0)  # FSK mark/space frequencies
    snr_threshold_db: float = 6.0  # Minimum SNR for covert tone isolation

@dataclass
class RFSensorConfig:
    """Software Defined Radio (SDR) Parameters (HackRF / RTL-SDR)."""
    center_freq_hz: float = 24.5e6  # 24.5 MHz (RAM bus fundamental leakage / RAMBO)
    secondary_freq_hz: float = 433.92e6  # 433.92 MHz ISM band
    sample_rate: float = 2.4e6  # 2.4 MSPS standard SDR IQ bandwidth
    gain_db: float = 38.0  # LNA / VGA gain
    fft_size: int = 2048  # Spectral resolution per RF slice
    covert_rf_burst_bandwidth_hz: float = 25000.0  # RAMBO burst bandwidth

@dataclass
class DSPOptimizationConfig:
    """Digital Signal Processing & Filter Parameters."""
    n_fft: int = 1024  # STFT window size
    hop_length: int = 256  # STFT hop size (75% overlap)
    window_type: str = "hann"  # Window function
    notch_filter_freqs: List[float] = field(default_factory=lambda: [50.0, 60.0, 100.0, 120.0])  # Mains power harmonics
    bandpass_acoustic_range: Tuple[float, float] = (300.0, 22000.0)  # Audible to near-ultrasound
    welch_nperseg: int = 512  # Segment length for PSD estimation
    waterfall_history_depth: int = 40  # Number of temporal FFT slices kept in waterfall matrix
    target_fps: int = 30  # Real-time UI rendering rate

@dataclass
class MLAutoencoderConfig:
    """PyTorch Deep Spectral Autoencoder Configuration."""
    input_shape: Tuple[int, int] = (40, 64)  # (Time slices, Frequency bins)
    latent_dim: int = 32  # Compressed latent bottleneck
    learning_rate: float = 1e-3
    batch_size: int = 32
    num_epochs: int = 25
    anomaly_threshold_std_multiplier: float = 2.5  # Dynamic threshold: Mean + k * StdDev (99% CI)
    model_save_path: str = os.path.join("evaluation_results", "autoencoder_best.pt")
    loss_function: str = "combined_mse_spectral"

@dataclass
class ServerRackLayoutConfig:
    """Server Room Rack Matrix Configuration for RSSI & TDoA Pinpointing."""
    # Server rack positions in meters (X, Y) within server room
    racks: Dict[str, Tuple[float, float]] = field(default_factory=lambda: {
        "Rack-Alpha": (1.0, 2.0),
        "Rack-Beta": (1.0, 5.0),
        "Rack-Gamma": (4.0, 2.0),
        "Rack-Delta": (4.0, 5.0),
        "Rack-Epsilon": (7.0, 2.0),
        "Rack-Zeta": (7.0, 5.0),
    })
    # Sensor node positions in meters (X, Y)
    sensor_nodes: Dict[str, Tuple[float, float]] = field(default_factory=lambda: {
        "Sensor-North": (4.0, 6.0),
        "Sensor-South": (4.0, 0.5),
        "Sensor-East": (8.0, 3.5),
        "Sensor-West": (0.5, 3.5),
    })
    path_loss_exponent: float = 2.2  # Indoor server room wireless/acoustic attenuation

@dataclass
class AlertingConfig:
    """Incident Response & Alert Logging Configuration."""
    log_dir: str = "logs"
    incident_log_file: str = os.path.join("logs", "aetherhound_incidents.jsonl")
    alert_cooldown_seconds: float = 1.0  # Prevent alert storming
    audio_buzzer_enabled: bool = True  # Edge hardware buzzer alert
    cli_flash_red_on_anomaly: bool = True

@dataclass
class AetherHoundConfig:
    """Master System Configuration."""
    acoustic: AcousticSensorConfig = field(default_factory=AcousticSensorConfig)
    rf: RFSensorConfig = field(default_factory=RFSensorConfig)
    dsp: DSPOptimizationConfig = field(default_factory=DSPOptimizationConfig)
    ml: MLAutoencoderConfig = field(default_factory=MLAutoencoderConfig)
    layout: ServerRackLayoutConfig = field(default_factory=ServerRackLayoutConfig)
    alerting: AlertingConfig = field(default_factory=AlertingConfig)
    version: str = "2.4.0-HARDENED"
    mode: str = "STANDALONE_AIRGAPPED"

# Global default instance
DEFAULT_CONFIG = AetherHoundConfig()
