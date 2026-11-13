"""
End-to-End System Integration Tests for AetherHound.
Verifies complete flow: Sensors -> DSP -> ML Inference -> Alert -> Pinpoint -> Demodulate.
"""

import os
import pytest
from aetherhound.engine.coordinator import PipelineCoordinator

def test_full_pipeline_flow():
    coordinator = PipelineCoordinator()
    # 1. Process normal baseline frame
    frame1 = coordinator.process_frame()
    assert "frame_index" in frame1
    assert "reconstruction_error" in frame1
    assert "threshold" in frame1
    assert "pinpointed_rack" in frame1
    assert frame1["cycle_latency_ms"] > 0

    # 2. Inject mock Fansmitter malware
    coordinator.emulator.set_fansmitter_state(active=True, rack="Rack-Delta", freq_hz=1950.0)
    frame2 = coordinator.process_frame()
    assert frame2["is_anomaly"]
    assert frame2["primary_peak_hz"] > 1800.0
    assert frame2["pinpointed_rack"] == "Rack-Delta"
    assert frame2["demodulated_text"] != ""

    # Check incident log was created
    assert os.path.exists(coordinator.config.alerting.incident_log_file)
