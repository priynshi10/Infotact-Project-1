"""
Incident Response & Alert Manager.
Handles structured logging of covert channel detections, edge buzzer alerts,
and incident dispatching for air-gapped security operations.
"""

import os
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from aetherhound.config import AlertingConfig

@dataclass
class IncidentReport:
    """Structured SIGINT Covert Channel Incident."""
    incident_id: str
    timestamp_utc: str
    timestamp_epoch: float
    channel_type: str  # 'ACOUSTIC_PWM' or 'RF_RAM_BUS'
    carrier_frequency_hz: float
    snr_db: float
    reconstruction_error: float
    detection_threshold: float
    pinpointed_rack: str
    confidence_score: float
    demodulated_payload: Optional[str] = None
    sensor_rssi_db: Optional[Dict[str, float]] = None

class AlertManager:
    """
    Manages alerting logic, edge buzzers, and JSONL log persistence.
    """

    def __init__(self, config: Optional[AlertingConfig] = None):
        self.config = config or AlertingConfig()
        os.makedirs(self.config.log_dir, exist_ok=True)
        self.log_file = self.config.incident_log_file
        self.last_alert_time = 0.0
        self.incident_history: List[IncidentReport] = []

    def dispatch_alert(
        self,
        channel_type: str,
        frequency_hz: float,
        snr_db: float,
        error: float,
        threshold: float,
        rack: str,
        confidence: float,
        demodulated_text: Optional[str] = None,
        rssi_map: Optional[Dict[str, float]] = None
    ) -> Optional[IncidentReport]:
        """
        Create, persist, and announce a verified covert channel incident.
        """
        now = time.time()
        if now - self.last_alert_time < self.config.alert_cooldown_seconds:
            return None  # Cooldown active to prevent alert flooding

        self.last_alert_time = now
        incident_id = f"INC-{int(now * 1000)}"
        timestamp_str = datetime.now(timezone.utc).isoformat()

        report = IncidentReport(
            incident_id=incident_id,
            timestamp_utc=timestamp_str,
            timestamp_epoch=now,
            channel_type=channel_type,
            carrier_frequency_hz=round(frequency_hz, 2),
            snr_db=round(snr_db, 2),
            reconstruction_error=round(error, 6),
            detection_threshold=round(threshold, 6),
            pinpointed_rack=rack,
            confidence_score=round(confidence, 3),
            demodulated_payload=demodulated_text,
            sensor_rssi_db=rssi_map
        )

        self.incident_history.append(report)

        # Append to JSONL audit log
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(report)) + "\n")

        # Edge hardware buzzer notification simulation
        if self.config.audio_buzzer_enabled:
            self._trigger_edge_buzzer()

        return report

    def _trigger_edge_buzzer(self) -> None:
        """Simulate hardware GPIO buzzer pulse on edge device (Raspberry Pi)."""
        pass  # In production, writes to GPIO pin 18

    def get_latest_incidents(self, limit: int = 10) -> List[IncidentReport]:
        """Return most recent incidents."""
        return self.incident_history[-limit:]
