"""
Active Countermeasures & Enterprise SIEM Integration Engine.
Provides autonomous acoustic noise masking to neutralize covert acoustic channels,
and formats ArcSight CEF and RFC 5424 Syslog records for unidirectional data diodes.
"""

import math
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from scipy.signal import butter, sosfilt

from aetherhound.engine.alert_manager import IncidentReport


class AcousticMaskingJammer:
    """
    Autonomous acoustic countermeasure that emits band-limited pink noise
    centered around detected covert acoustic exfiltration frequencies
    (e.g., Fansmitter, DiskFiltration) to reduce signal-to-noise ratio below decodable thresholds.
    """

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = sample_rate

    def generate_masking_noise(
        self,
        center_freq_hz: float,
        bandwidth_hz: float = 400.0,
        duration_sec: float = 0.5,
        target_amplitude: float = 0.4
    ) -> np.ndarray:
        """
        Generate bandpass-filtered acoustic noise centered on target exfiltration carrier.
        Suppresses the covert channel's SNR at the adversary microphone.
        """
        n_samples = int(self.sample_rate * duration_sec)
        # 1. Generate base Gaussian white noise
        white_noise = np.random.normal(0, 1.0, n_samples).astype(np.float32)

        # 2. Design 4th-order Butterworth bandpass around target carrier
        nyquist = 0.5 * self.sample_rate
        low = max(20.0, center_freq_hz - (bandwidth_hz / 2.0)) / nyquist
        high = min(self.sample_rate / 2.0 - 50.0, center_freq_hz + (bandwidth_hz / 2.0)) / nyquist

        if low >= high or low <= 0 or high >= 1.0:
            # Fallback to normalized broadband noise
            masking_signal = white_noise / (np.max(np.abs(white_noise)) + 1e-6)
            return (masking_signal * target_amplitude).astype(np.float32)

        sos = butter(4, [low, high], btype='bandpass', output='sos')
        band_noise = sosfilt(sos, white_noise)

        # 3. Scale to target masking amplitude
        peak = np.max(np.abs(band_noise))
        if peak > 0:
            band_noise = band_noise / peak
        return (band_noise * target_amplitude).astype(np.float32)

    def calculate_mitigation_snr(
        self,
        covert_signal: np.ndarray,
        masking_noise: np.ndarray
    ) -> float:
        """
        Calculate resulting signal-to-noise ratio (SNR in dB) after acoustic jamming.
        Returns SNR in dB. Successful mitigation drops SNR < 0 dB.
        """
        min_len = min(len(covert_signal), len(masking_noise))
        sig = covert_signal[:min_len]
        noise = masking_noise[:min_len]

        p_signal = np.mean(sig ** 2) + 1e-12
        p_noise = np.mean(noise ** 2) + 1e-12

        snr_db = 10.0 * np.log10(p_signal / p_noise)
        return float(snr_db)


class SIEMEventExporter:
    """
    Formats SIGINT incident reports into standard formats for export
    across air-gapped optical unidirectional data diodes to central SIEMs (Splunk, ArcSight, QRadar).
    """

    DEVICE_VENDOR = "Infotact Solutions"
    DEVICE_PRODUCT = "AetherHound"
    DEVICE_VERSION = "1.0"

    @classmethod
    def format_cef(cls, incident: IncidentReport) -> str:
        """
        Generate Micro Focus ArcSight Common Event Format (CEF) string.
        Format: CEF:Version|Device Vendor|Device Product|Device Version|Signature ID|Name|Severity|Extension
        """
        severity = 8 if incident.snr_db > 12.0 else 6
        sig_id = f"COVERT-{incident.channel_type}"
        name = f"Air-Gapped Covert Channel Detected ({incident.channel_type})"

        extensions = [
            f"src={incident.pinpointed_rack}",
            f"cs1={incident.channel_type}",
            "cs1Label=ChannelType",
            f"cn1={incident.snr_db:.2f}",
            "cn1Label=SNR_dB",
            f"cn2={incident.carrier_frequency_hz:.1f}",
            "cn2Label=CarrierFrequency_Hz",
            f"cfp1={incident.confidence_score:.3f}",
            "cfp1Label=LocalizationConfidence",
            f"externalId={incident.incident_id}",
            f"rt={int(incident.timestamp_epoch * 1000)}"
        ]

        if incident.demodulated_payload:
            clean_payload = incident.demodulated_payload.replace("=", ":")
            extensions.append(f"cs2={clean_payload}")
            extensions.append("cs2Label=DemodulatedPayload")

        ext_str = " ".join(extensions)
        return f"CEF:0|{cls.DEVICE_VENDOR}|{cls.DEVICE_PRODUCT}|{cls.DEVICE_VERSION}|{sig_id}|{name}|{severity}|{ext_str}"

    @classmethod
    def format_syslog_rfc5424(cls, incident: IncidentReport) -> str:
        """
        Generate RFC 5424 compliant Syslog record for optical data diode streaming.
        Facility: local0 (16), Severity: warning (4) -> Priority = 16 * 8 + 4 = 132
        """
        timestamp = incident.timestamp_utc
        pri = 132
        app_name = "aetherhound"
        proc_id = "sensor-01"
        msg_id = incident.incident_id

        sd_params = (
            f'channel="{incident.channel_type}" '
            f'rack="{incident.pinpointed_rack}" '
            f'freq_hz="{incident.carrier_frequency_hz:.1f}" '
            f'snr_db="{incident.snr_db:.2f}" '
            f'conf="{incident.confidence_score:.3f}"'
        )
        structured_data = f'[sigint@43210 {sd_params}]'
        message = f"Covert channel exfiltration attempt intercepted at {incident.pinpointed_rack} on {incident.carrier_frequency_hz:.1f}Hz"

        return f"<{pri}>1 {timestamp} aetherhound-edge {app_name} {proc_id} {msg_id} {structured_data} {message}"
