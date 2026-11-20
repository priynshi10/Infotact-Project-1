"""Loopback HTTP API for the existing AetherHound real-time detection engine."""

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import threading
from typing import Any, Deque, Dict, List, NotRequired, Optional, TypedDict
from urllib.parse import urlsplit

from aetherhound.core.evidence_metadata import (
    SOURCE_TYPE_LIVE_HARDWARE,
    SOURCE_TYPE_RECORDED_HARDWARE,
    SOURCE_TYPE_SYNTHETIC_SIMULATION,
    normalize_source_type,
)
from aetherhound.core.realtime_engine import RealtimeEngine


LOGGER = logging.getLogger("aetherhound.api")
MAX_HISTORY = 500
EVENT_LOGS = {
    "rf_events.jsonl": "RF_ALERT",
    "acoustic_events.jsonl": "ACOUSTIC_ALERT",
    "morse_events.jsonl": "MORSE_ALERT",
}
EVENT_MODALITIES = {
    "RF_ALERT": "RF",
    "ACOUSTIC_ALERT": "ACOUSTIC",
    "MORSE_ALERT": "ACOUSTIC",
}
SOURCE_TYPES = {
    SOURCE_TYPE_LIVE_HARDWARE,
    SOURCE_TYPE_RECORDED_HARDWARE,
    SOURCE_TYPE_SYNTHETIC_SIMULATION,
}


class MonitoringState(TypedDict):
    status: str
    running: bool
    paused: bool
    uptime_sec: float


class SensorState(TypedDict):
    sensor_id: str
    connected: bool
    status: str
    source_type: Optional[str]
    processed_count: int
    metrics: Dict[str, Optional[float]]
    morse_status: NotRequired[Optional[str]]


class MonitoringSummary(TypedDict):
    total_detections: int
    active_alerts: int
    latest_detection_timestamp: Optional[str]


class MonitoringResponse(TypedDict):
    schema_version: int
    server_status: str
    updated_at: str
    monitoring: MonitoringState
    rf: SensorState
    acoustic: SensorState
    summary: MonitoringSummary
    detections: List[Dict[str, Any]]


@dataclass(frozen=True)
class DetectionRecord:
    """Sanitized detection event response matching fields available from detectors."""

    event_id: str
    capture_id: Optional[str]
    timestamp: Optional[str]
    timestamp_epoch: Optional[float]
    modality: str
    source_type: Optional[str]
    detection_type: Optional[str]
    detection_status: Optional[str]
    sensor_id: Optional[str]
    confidence_score: Optional[float]
    metrics: Dict[str, Any]
    evidence_ref: Optional[str]
    verification_status: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _finite_number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        normalized = float(value)
    except (OverflowError, ValueError):
        return None
    if not math.isfinite(normalized):
        return None
    return normalized


def _source_type(payload: Dict[str, Any]) -> Optional[str]:
    explicit_source = payload.get("source_type")
    candidates = set()
    if isinstance(explicit_source, str) and explicit_source in SOURCE_TYPES:
        candidates.add(explicit_source)
    if explicit_source is not None:
        if not candidates:
            return None

    synthetic = payload.get("is_synthetic")
    if synthetic is not None and not isinstance(synthetic, bool):
        return None

    for field in ("data_source", "source_mode", "source"):
        label = payload.get(field)
        if label is None or label == "":
            continue
        if not isinstance(label, str):
            return None
        source_type = normalize_source_type(label)
        if source_type is None and field == "source" and isinstance(label, str):
            source_type = {
                "LIVE MICROPHONE": SOURCE_TYPE_LIVE_HARDWARE,
                "SYNTHETIC TEST": SOURCE_TYPE_SYNTHETIC_SIMULATION,
            }.get(label.strip().upper())
        if source_type is None:
            return None
        candidates.add(source_type)

    if synthetic is True:
        candidates.add(SOURCE_TYPE_SYNTHETIC_SIMULATION)

    return candidates.pop() if len(candidates) == 1 else None


def _safe_evidence_ref(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("evidence_ref", "raw_data_path", "data_file", "raw_iq_binding", "raw_capture_binding"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return Path(value.replace("\\", "/")).name or None
    return None


def _event_metrics(event_kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if event_kind == "RF_ALERT":
        keys = (
            "detected_freq_hz",
            "signal_power_db",
            "noise_floor_db",
            "deviation_db",
            "sigma_deviation",
            "persistence_windows",
        )
        evidence_keys = ("peak_bin", "noise_std_db", "total_peaks")
    elif event_kind == "ACOUSTIC_ALERT":
        keys = ("dominant_frequency_hz", "rms_energy", "pulse_count", "pattern_duration_sec")
        evidence_keys = ("energy_ratio", "mean_periodicity", "baseline_rms", "spectral_centroid_hz")
    else:
        keys = ("target_pattern", "decoded_morse", "detection_method")
        evidence_keys = (
            "mean_timing_error_pct",
            "timing_accuracy",
            "symbol_count",
            "dot_ref_sec",
            "dash_ref_sec",
        )

    metrics: Dict[str, Any] = {}
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            metrics[key] = value
        elif _finite_number(value) is not None:
            metrics[key] = value

    evidence = payload.get("evidence")
    if isinstance(evidence, dict):
        for key in evidence_keys:
            value = evidence.get(key)
            if isinstance(value, str):
                metrics[key] = value
            elif _finite_number(value) is not None:
                metrics[key] = value

    return metrics


def map_detector_event(event_kind: str, payload: Dict[str, Any]) -> Optional[DetectionRecord]:
    """Map one existing detector event to a safe, frontend-facing response record."""
    modality = EVENT_MODALITIES.get(event_kind)
    if modality is None or not isinstance(payload, dict):
        return None

    timestamp_epoch = _finite_number(payload.get("timestamp"))
    timestamp = None
    if timestamp_epoch is not None:
        try:
            timestamp = datetime.fromtimestamp(timestamp_epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (OverflowError, OSError, ValueError):
            timestamp_epoch = None

    confidence_score = _finite_number(payload.get("match_score")) if event_kind == "MORSE_ALERT" else None
    if confidence_score is not None and not 0.0 <= confidence_score <= 1.0:
        confidence_score = None

    detection_type = payload.get("event_type")
    if not isinstance(detection_type, str):
        detection_type = None

    detection_status = payload.get("status", payload.get("result"))
    if not isinstance(detection_status, str):
        detection_status = None

    sensor_id = payload.get("sensor_id")
    if not isinstance(sensor_id, str):
        sensor_id = None

    capture_id = payload.get("capture_id")
    if not isinstance(capture_id, str) or not capture_id.strip():
        capture_id = None

    verification_status = payload.get("verification_status")
    if not isinstance(verification_status, str):
        verification_status = None

    metrics = _event_metrics(event_kind, payload)
    event_identity = {
        "kind": event_kind,
        "timestamp": timestamp_epoch,
        "sensor_id": sensor_id,
        "detection_type": detection_type,
        "capture_id": capture_id,
        "source_type": _source_type(payload),
        "metrics": metrics,
    }
    event_id = hashlib.sha256(
        json.dumps(event_identity, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()

    return DetectionRecord(
        event_id=event_id,
        capture_id=capture_id,
        timestamp=timestamp,
        timestamp_epoch=timestamp_epoch,
        modality=modality,
        source_type=_source_type(payload),
        detection_type=detection_type,
        detection_status=detection_status,
        sensor_id=sensor_id,
        confidence_score=confidence_score,
        metrics=metrics,
        evidence_ref=_safe_evidence_ref(payload),
        verification_status=verification_status,
    )


class DetectionService:
    """Owns the real-time engine and returns bounded, deduplicated event history."""

    def __init__(
        self,
        data_dir: str = "data",
        engine: Optional[RealtimeEngine] = None,
    ):
        self.data_dir = Path(data_dir)
        self.engine = engine or RealtimeEngine(
            synthetic_rf=False,
            synthetic_audio=False,
            data_dir=str(self.data_dir),
        )
        self._history: Deque[DetectionRecord] = deque(maxlen=MAX_HISTORY)
        self._event_ids = set()
        self._total_detections = 0
        self._history_lock = threading.Lock()

        self._load_history()
        self.engine.register_event_callback(self._on_engine_event)

    def _add_record(self, record: DetectionRecord) -> None:
        with self._history_lock:
            if record.event_id in self._event_ids:
                return
            self._event_ids.add(record.event_id)
            self._history.append(record)
            self._total_detections += 1

    def _load_history(self) -> None:
        events_dir = self.data_dir / "events"
        for filename, event_kind in EVENT_LOGS.items():
            path = events_dir / filename
            try:
                source_file = path.open("r", encoding="utf-8")
            except FileNotFoundError:
                continue
            except OSError as exc:
                LOGGER.warning("Could not read event history file %s: %s", path.name, exc)
                continue

            with source_file:
                for line_number, line in enumerate(source_file, start=1):
                    if not line.strip():
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError as exc:
                        LOGGER.warning("Skipping malformed event record in %s at line %d: %s", path.name, line_number, exc)
                        continue
                    if not isinstance(payload, dict):
                        LOGGER.warning("Skipping non-object event record in %s at line %d", path.name, line_number)
                        continue
                    record = map_detector_event(event_kind, payload)
                    if record is not None:
                        self._add_record(record)

    def _on_engine_event(self, event_kind: str, payload: Dict[str, Any]) -> None:
        record = map_detector_event(event_kind, payload)
        if record is not None:
            self._add_record(record)

    def control(self, action: str) -> None:
        if action == "start":
            self.engine.start()
        elif action == "pause":
            if not self.engine.is_running:
                raise RuntimeError("Cannot pause monitoring before it is started")
            self.engine.pause()
        elif action == "resume":
            if not self.engine.is_running:
                raise RuntimeError("Cannot resume monitoring before it is started")
            self.engine.resume()
        elif action == "stop":
            self.engine.stop()
        else:
            raise ValueError(f"Unsupported monitoring action: {action}")

    def snapshot(self) -> MonitoringResponse:
        telemetry = self.engine.get_telemetry()
        running = self.engine.is_running
        paused = self.engine.is_paused

        rf_processed = telemetry.rf_windows_processed > 0
        acoustic_processed = telemetry.acoustic_chunks_processed > 0
        rf_status = self._sensor_status(
            running, paused, telemetry.rf_connected, rf_processed, telemetry.rf_status
        )
        acoustic_status = self._sensor_status(
            running, paused, telemetry.mic_connected, acoustic_processed, telemetry.acoustic_status
        )

        if not running:
            monitoring_status = "STOPPED"
        elif paused:
            monitoring_status = "PAUSED"
        elif telemetry.rf_connected and telemetry.mic_connected:
            monitoring_status = "ACTIVE"
        elif telemetry.rf_connected or telemetry.mic_connected:
            monitoring_status = "DEGRADED"
        else:
            monitoring_status = "NO SENSORS"

        latest_rf = self.engine.rf_processor.latest_processed if rf_processed else None
        latest_acoustic = self.engine.acoustic_processor.latest_processed if acoustic_processed else None
        rf_source = self._sample_source_type(latest_rf)
        acoustic_source = self._sample_source_type(latest_acoustic)

        rf_metrics = {
            "center_freq_hz": telemetry.rf_center_freq_hz if rf_processed else None,
            "sample_rate_hz": telemetry.rf_sample_rate_hz if rf_processed else None,
            "noise_floor_db": telemetry.rf_noise_floor_db if rf_processed else None,
            "peak_power_db": telemetry.rf_peak_power_db if rf_processed else None,
            "peak_freq_hz": telemetry.rf_peak_freq_hz if rf_processed else None,
            "processing_latency_ms": telemetry.rf_processing_latency_ms if rf_processed else None,
        }
        acoustic_metrics = {
            "sample_rate_hz": telemetry.acoustic_sample_rate_hz if acoustic_processed else None,
            "rms_energy": telemetry.acoustic_rms_energy if acoustic_processed else None,
            "dominant_frequency_hz": telemetry.acoustic_dominant_freq_hz if acoustic_processed else None,
            "processing_latency_ms": telemetry.acoustic_processing_latency_ms if acoustic_processed else None,
            "chunk_size": len(latest_acoustic.raw_samples) if latest_acoustic is not None else None,
            "periodicity_score": latest_acoustic.features.periodicity_score if latest_acoustic is not None else None,
        }

        with self._history_lock:
            records = sorted(
                self._history,
                key=lambda record: record.timestamp_epoch if record.timestamp_epoch is not None else -1.0,
                reverse=True,
            )
            total_detections = self._total_detections
            detections = [record.to_dict() for record in records]

        latest_detection_timestamp = detections[0]["timestamp"] if detections else None
        active_alert_count = sum(status == "SUSPICIOUS" for status in (rf_status, acoustic_status))

        return {
            "schema_version": 1,
            "server_status": "AVAILABLE",
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "monitoring": {
                "status": monitoring_status,
                "running": running,
                "paused": paused,
                "uptime_sec": telemetry.uptime_sec if running else 0.0,
            },
            "rf": {
                "sensor_id": self.engine.rf_detector.sensor_id,
                "connected": telemetry.rf_connected,
                "status": rf_status,
                "source_type": rf_source,
                "processed_count": telemetry.rf_windows_processed,
                "metrics": rf_metrics,
            },
            "acoustic": {
                "sensor_id": self.engine.acoustic_detector.sensor_id,
                "connected": telemetry.mic_connected,
                "status": acoustic_status,
                "morse_status": telemetry.morse_status if acoustic_processed else None,
                "source_type": acoustic_source,
                "processed_count": telemetry.acoustic_chunks_processed,
                "metrics": acoustic_metrics,
            },
            "summary": {
                "total_detections": total_detections,
                "active_alerts": active_alert_count,
                "latest_detection_timestamp": latest_detection_timestamp,
            },
            "detections": detections,
        }

    @staticmethod
    def _sample_source_type(processed: Any) -> Optional[str]:
        if processed is None:
            return None
        provenance = {
            field: value
            for field in ("source_type", "data_source", "source_mode", "source", "is_synthetic")
            if (value := getattr(processed, field, None)) is not None
        }
        return _source_type(provenance)

    @staticmethod
    def _sensor_status(
        running: bool,
        paused: bool,
        connected: bool,
        processed: bool,
        detector_status: str,
    ) -> str:
        if not running:
            return "STOPPED"
        if paused:
            return "PAUSED"
        if not connected:
            return "DISCONNECTED"
        if not processed:
            return "AWAITING DATA"
        return "SUSPICIOUS" if detector_status == "SUSPICIOUS" else "NORMAL"


def create_server(
    service: DetectionService,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> ThreadingHTTPServer:
    class MonitoringRequestHandler(BaseHTTPRequestHandler):
        def _send_json(self, status_code: int, data: Dict[str, Any]) -> None:
            body = json.dumps(data, separators=(",", ":"), allow_nan=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            route = urlsplit(self.path).path
            if route == "/api/health":
                self._send_json(200, {"status": "AVAILABLE"})
            elif route == "/api/monitoring":
                self._send_json(200, service.snapshot())
            else:
                self._send_json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            route = urlsplit(self.path).path
            action = route.removeprefix("/api/monitoring/")
            if not route.startswith("/api/monitoring/") or action not in {"start", "pause", "resume", "stop"}:
                self._send_json(404, {"error": "Not found"})
                return
            origin = self.headers.get("Origin")
            if origin is not None and origin not in {
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            }:
                self._send_json(403, {"error": "Monitoring controls accept requests only from the local dashboard"})
                return
            try:
                service.control(action)
            except RuntimeError as exc:
                self._send_json(409, {"error": str(exc)})
                return
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, service.snapshot())

        def log_message(self, format_string: str, *args: Any) -> None:
            LOGGER.info("%s - %s", self.address_string(), format_string % args)

    return ThreadingHTTPServer((host, port), MonitoringRequestHandler)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    project_data_dir = Path(__file__).resolve().parents[1] / "data"
    port = int(os.getenv("AETHERHOUND_API_PORT", "8765"))
    service = DetectionService(data_dir=str(project_data_dir))
    server = create_server(service, port=port)
    LOGGER.info("AetherHound API listening on http://127.0.0.1:%d", port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Stopping AetherHound API")
    finally:
        if service.engine.is_running:
            service.engine.stop()
        server.server_close()


if __name__ == "__main__":
    main()
