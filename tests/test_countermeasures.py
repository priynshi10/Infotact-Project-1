"""
Unit tests for AetherHound Countermeasures and SIEM Event Exporters.
Verifies acoustic noise masking generation, mitigation SNR drop, and CEF / Syslog RFC 5424 compliance.
"""

import numpy as np
import pytest
from aetherhound.engine.alert_manager import IncidentReport
from aetherhound.engine.countermeasures import AcousticMaskingJammer, SIEMEventExporter


def test_acoustic_masking_generation():
    jammer = AcousticMaskingJammer(sample_rate=48000)
    center_freq = 1800.0
    duration = 0.1
    noise = jammer.generate_masking_noise(center_freq_hz=center_freq, duration_sec=duration)

    expected_len = int(48000 * duration)
    assert len(noise) == expected_len
    assert np.max(np.abs(noise)) <= 0.45
    assert np.var(noise) > 0.001


def test_acoustic_masking_snr_drop():
    jammer = AcousticMaskingJammer(sample_rate=48000)
    # Synthesize weak covert carrier signal
    t = np.linspace(0, 0.1, int(48000 * 0.1), endpoint=False)
    covert_signal = 0.05 * np.sin(2.0 * np.pi * 1500.0 * t).astype(np.float32)

    # Generate aggressive masking noise
    masking_noise = jammer.generate_masking_noise(center_freq_hz=1500.0, duration_sec=0.1, target_amplitude=0.4)

    # Post-mitigation SNR should drop well below 0 dB
    snr_db = jammer.calculate_mitigation_snr(covert_signal, masking_noise)
    assert snr_db < 0.0, f"Expected SNR < 0 dB, got {snr_db:.2f} dB"


def test_siem_cef_export_format():
    incident = IncidentReport(
        incident_id="INC-TEST-001",
        timestamp_utc="2026-11-23T09:20:00Z",
        timestamp_epoch=1795415400.0,
        channel_type="ACOUSTIC_PWM_FAN",
        carrier_frequency_hz=1950.5,
        snr_db=18.4,
        reconstruction_error=0.0345,
        detection_threshold=0.0120,
        pinpointed_rack="RACK-03",
        confidence_score=0.942,
        demodulated_payload="FLAG{AIR_GAP_1337}"
    )

    cef = SIEMEventExporter.format_cef(incident)
    assert cef.startswith("CEF:0|Infotact Solutions|AetherHound|1.0|COVERT-ACOUSTIC_PWM_FAN|")
    assert "src=RACK-03" in cef
    assert "cn1=18.40" in cef
    assert "cn2=1950.5" in cef
    assert "externalId=INC-TEST-001" in cef
    assert "cs2=FLAG{AIR_GAP_1337}" in cef


def test_siem_syslog_rfc5424_format():
    incident = IncidentReport(
        incident_id="INC-TEST-002",
        timestamp_utc="2026-11-23T09:20:00Z",
        timestamp_epoch=1795415400.0,
        channel_type="RF_RAMBO",
        carrier_frequency_hz=24500000.0,
        snr_db=22.1,
        reconstruction_error=0.0512,
        detection_threshold=0.0150,
        pinpointed_rack="RACK-05",
        confidence_score=0.887,
        demodulated_payload="SECRET_KEY"
    )

    syslog = SIEMEventExporter.format_syslog_rfc5424(incident)
    assert syslog.startswith("<132>1 2026-11-23T09:20:00Z aetherhound-edge aetherhound sensor-01 INC-TEST-002")
    assert '[sigint@43210' in syslog
    assert 'channel="RF_RAMBO"' in syslog
    assert 'rack="RACK-05"' in syslog
