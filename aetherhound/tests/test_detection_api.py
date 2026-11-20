import json
import threading
from types import SimpleNamespace
from urllib.request import urlopen

from aetherhound.api import DetectionService, create_server, map_detector_event
from aetherhound.core.evidence_metadata import (
    SOURCE_TYPE_LIVE_HARDWARE,
    SOURCE_TYPE_RECORDED_HARDWARE,
    SOURCE_TYPE_SYNTHETIC_SIMULATION,
)
from aetherhound.core.realtime_engine import RealtimeEngine


def test_rf_detection_mapping_preserves_synthetic_source_and_metrics():
    record = map_detector_event(
        "RF_ALERT",
        {
            "event_type": "Unusual RF Spectral Activity",
            "sensor_id": "SDR-01",
            "detected_freq_hz": 434_070_000.0,
            "signal_power_db": -2.5,
            "noise_floor_db": -57.9,
            "deviation_db": 55.4,
            "sigma_deviation": 11.3,
            "persistence_windows": 3,
            "timestamp": 1794469280.4,
            "is_synthetic": True,
            "evidence": {"peak_bin": 1174},
        },
    )

    assert record is not None
    assert record.modality == "RF"
    assert record.source_type == SOURCE_TYPE_SYNTHETIC_SIMULATION
    assert record.capture_id is None
    assert record.confidence_score is None
    assert record.metrics["detected_freq_hz"] == 434_070_000.0
    assert record.metrics["sigma_deviation"] == 11.3
    assert record.timestamp == "2026-11-12T07:41:20Z"


def test_acoustic_and_morse_detection_mapping_uses_real_confidence_only():
    acoustic = map_detector_event(
        "ACOUSTIC_ALERT",
        {
            "event_type": "Structured Acoustic Repetitive Pulses",
            "sensor_id": "MIC-01",
            "dominant_frequency_hz": 1820.5,
            "rms_energy": 0.1482,
            "pulse_count": 9,
            "pattern_duration_sec": 6.2,
            "timestamp": 1794469130.1,
            "is_synthetic": False,
            "source_type": SOURCE_TYPE_LIVE_HARDWARE,
        },
    )
    morse = map_detector_event(
        "MORSE_ALERT",
        {
            "event_type": "Covert Acoustic Morse Channel Detected",
            "sensor_id": "MIC-01",
            "target_pattern": "SOS",
            "decoded_morse": "... --- ...",
            "match_score": 0.89,
            "timestamp": 1794469136.214,
            "source": "SYNTHETIC TEST",
        },
    )

    assert acoustic is not None
    assert acoustic.modality == "ACOUSTIC"
    assert acoustic.source_type == SOURCE_TYPE_LIVE_HARDWARE
    assert acoustic.confidence_score is None
    assert acoustic.metrics["dominant_frequency_hz"] == 1820.5
    assert morse is not None
    assert morse.source_type == SOURCE_TYPE_SYNTHETIC_SIMULATION
    assert morse.confidence_score == 0.89
    assert morse.metrics["decoded_morse"] == "... --- ..."


def test_mapping_does_not_invent_missing_metadata_and_sanitizes_evidence_ref():
    record = map_detector_event(
        "RF_ALERT",
        {
            "event_type": "Unusual RF Spectral Activity",
            "timestamp": 1794469280.4,
            "raw_iq_binding": r"C:\private\captures\capture.npy",
        },
    )

    assert record is not None
    assert record.source_type is None
    assert record.capture_id is None
    assert record.sensor_id is None
    assert record.evidence_ref == "capture.npy"
    assert record.verification_status is None
    assert record.confidence_score is None

    recorded = map_detector_event(
        "RF_ALERT",
        {
            "event_type": "Recorded RF event",
            "source_type": SOURCE_TYPE_RECORDED_HARDWARE,
            "timestamp": 1794469280.4,
        },
    )
    assert recorded is not None
    assert recorded.source_type == SOURCE_TYPE_RECORDED_HARDWARE

    invalid_source = map_detector_event(
        "RF_ALERT",
        {
            "event_type": "Unknown source",
            "source_type": "UNKNOWN",
            "is_synthetic": False,
            "timestamp": 1794469280.4,
        },
    )
    assert invalid_source is not None
    assert invalid_source.source_type is None


def test_source_classification_requires_explicit_hardware_provenance():
    cases = (
        ({"source_type": SOURCE_TYPE_LIVE_HARDWARE, "is_synthetic": False}, SOURCE_TYPE_LIVE_HARDWARE),
        ({"source_type": SOURCE_TYPE_RECORDED_HARDWARE, "is_synthetic": False}, SOURCE_TYPE_RECORDED_HARDWARE),
        (
            {"source_type": SOURCE_TYPE_SYNTHETIC_SIMULATION, "is_synthetic": False},
            SOURCE_TYPE_SYNTHETIC_SIMULATION,
        ),
        (
            {
                "source_type": SOURCE_TYPE_LIVE_HARDWARE,
                "data_source": "LIVE HARDWARE",
                "is_synthetic": False,
            },
            SOURCE_TYPE_LIVE_HARDWARE,
        ),
        (
            {
                "source_type": SOURCE_TYPE_RECORDED_HARDWARE,
                "data_source": "RECORDED HARDWARE",
                "is_synthetic": False,
            },
            SOURCE_TYPE_RECORDED_HARDWARE,
        ),
        ({"source_type": SOURCE_TYPE_LIVE_HARDWARE, "is_synthetic": True}, None),
        ({"source_type": SOURCE_TYPE_RECORDED_HARDWARE, "is_synthetic": True}, None),
        (
            {"source_type": SOURCE_TYPE_SYNTHETIC_SIMULATION, "is_synthetic": True},
            SOURCE_TYPE_SYNTHETIC_SIMULATION,
        ),
        ({"source_type": SOURCE_TYPE_RECORDED_HARDWARE, "data_source": "LIVE HARDWARE"}, None),
        ({"is_synthetic": True}, SOURCE_TYPE_SYNTHETIC_SIMULATION),
        ({"is_synthetic": False}, None),
        ({}, None),
        ({"data_source": "RECORDED HARDWARE"}, SOURCE_TYPE_RECORDED_HARDWARE),
        ({"data_source": "LIVE HARDWARE", "is_synthetic": True}, None),
        ({"data_source": "UNKNOWN", "is_synthetic": True}, None),
        ({"data_source": "LIVE HARDWARE", "is_synthetic": "false"}, None),
        ({"source_type": "UNKNOWN", "is_synthetic": True}, None),
    )

    for provenance, expected_source in cases:
        record = map_detector_event("RF_ALERT", {"event_type": "RF event", **provenance})
        assert record is not None
        assert record.source_type == expected_source


def test_sample_source_classification_does_not_treat_non_synthetic_as_live():
    assert DetectionService._sample_source_type(SimpleNamespace(is_synthetic=True)) == SOURCE_TYPE_SYNTHETIC_SIMULATION
    assert DetectionService._sample_source_type(SimpleNamespace(is_synthetic=False)) is None
    assert DetectionService._sample_source_type(SimpleNamespace(source_type=SOURCE_TYPE_RECORDED_HARDWARE)) == (
        SOURCE_TYPE_RECORDED_HARDWARE
    )
    assert DetectionService._sample_source_type(
        SimpleNamespace(data_source="LIVE HARDWARE", is_synthetic=True)
    ) is None
    assert DetectionService._sample_source_type(
        SimpleNamespace(source_type=SOURCE_TYPE_LIVE_HARDWARE, is_synthetic=False)
    ) == SOURCE_TYPE_LIVE_HARDWARE


def test_empty_backend_snapshot_reports_unavailable_sensors_without_fake_metrics(tmp_path):
    engine = RealtimeEngine(data_dir=str(tmp_path / "data"))
    service = DetectionService(data_dir=str(tmp_path / "data"), engine=engine)
    snapshot = service.snapshot()

    assert snapshot["server_status"] == "AVAILABLE"
    assert snapshot["monitoring"]["status"] == "STOPPED"
    assert snapshot["rf"]["status"] == "STOPPED"
    assert snapshot["acoustic"]["status"] == "STOPPED"
    assert snapshot["rf"]["source_type"] is None
    assert snapshot["rf"]["metrics"]["peak_freq_hz"] is None
    assert snapshot["acoustic"]["metrics"]["rms_energy"] is None
    assert snapshot["summary"] == {
        "total_detections": 0,
        "active_alerts": 0,
        "latest_detection_timestamp": None,
    }
    assert snapshot["detections"] == []


def test_synthetic_engine_snapshot_never_claims_physical_connection(tmp_path):
    from aetherhound.core.evidence_metadata import SOURCE_TYPE_SYNTHETIC_SIMULATION

    engine = RealtimeEngine(
        synthetic_rf=True,
        synthetic_audio=True,
        data_dir=str(tmp_path / "data"),
    )
    service = DetectionService(data_dir=str(tmp_path / "data"), engine=engine)
    engine.start()
    try:
        import time

        time.sleep(0.35)
        snapshot = service.snapshot()
        assert snapshot["rf"]["connected"] is False
        assert snapshot["acoustic"]["connected"] is False
        assert snapshot["rf"]["source_type"] == SOURCE_TYPE_SYNTHETIC_SIMULATION
        assert snapshot["acoustic"]["source_type"] == SOURCE_TYPE_SYNTHETIC_SIMULATION
        assert snapshot["rf"]["processed_count"] > 0
        assert snapshot["acoustic"]["processed_count"] > 0
    finally:
        engine.stop()


def test_history_deduplicates_persisted_and_polled_events(tmp_path):
    data_dir = tmp_path / "data"
    events_dir = data_dir / "events"
    events_dir.mkdir(parents=True)
    payload = {
        "event_type": "Unusual RF Spectral Activity",
        "sensor_id": "SDR-01",
        "detected_freq_hz": 434_070_000.0,
        "timestamp": 1794469280.4,
        "is_synthetic": True,
    }
    event_line = json.dumps(payload)
    (events_dir / "rf_events.jsonl").write_text(f"{event_line}\n{event_line}\n", encoding="utf-8")

    engine = RealtimeEngine(data_dir=str(data_dir))
    service = DetectionService(data_dir=str(data_dir), engine=engine)
    service._on_engine_event("RF_ALERT", payload)
    service._on_engine_event("RF_ALERT", payload)
    snapshot = service.snapshot()

    assert snapshot["summary"]["total_detections"] == 1
    assert len(snapshot["detections"]) == 1


def test_http_monitoring_endpoint_returns_empty_snapshot(tmp_path):
    engine = RealtimeEngine(data_dir=str(tmp_path / "data"))
    service = DetectionService(data_dir=str(tmp_path / "data"), engine=engine)
    server = create_server(service, port=0)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/api/monitoring", timeout=2) as response:
            snapshot = json.loads(response.read().decode("utf-8"))
        assert snapshot["server_status"] == "AVAILABLE"
        assert snapshot["detections"] == []
        assert snapshot["rf"]["status"] == "STOPPED"
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)

def test_monitoring_post_origin_validation(tmp_path):
    class StubService:
        def __init__(self):
            self.actions = []

        def control(self, action):
            self.actions.append(action)

        def snapshot(self):
            return {"status": "OK"}

    service = StubService()
    server = create_server(service, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        base_url = f"http://127.0.0.1:{server.server_port}"

        for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
            request = __import__("urllib.request", fromlist=["Request"]).Request(
                f"{base_url}/api/monitoring/start",
                headers={"Origin": origin},
                method="POST",
            )
            with urlopen(request, timeout=2) as response:
                assert response.status == 200

        assert service.actions == ["start", "start"]

        request = __import__("urllib.request", fromlist=["Request"]).Request(
            f"{base_url}/api/monitoring/stop",
            headers={"Origin": "http://evil.example"},
            method="POST",
        )
        try:
            urlopen(request, timeout=2)
            assert False, "Unapproved Origin should be rejected"
        except __import__("urllib.error", fromlist=["HTTPError"]).HTTPError as error:
            assert error.code == 403

        assert service.actions == ["start", "start"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
