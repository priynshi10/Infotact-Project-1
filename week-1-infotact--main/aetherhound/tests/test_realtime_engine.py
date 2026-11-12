"""
Integration tests for the AetherHound Real-Time Core Engine.
"""

import os
import time
import pytest

from aetherhound.core.realtime_engine import RealtimeEngine
from aetherhound.hardware.config import HardwareConfig


def test_realtime_engine_lifecycle_and_telemetry(tmp_path):
    cfg = HardwareConfig()
    engine = RealtimeEngine(
        config=cfg,
        synthetic_rf=True,
        synthetic_audio=True,
        data_dir=str(tmp_path / "data"),
    )

    # 1. Start engine
    assert engine.start() is True
    assert engine.is_running is True

    # 2. Let it run for 1.5 seconds to acquire and process several windows
    time.sleep(1.5)

    tel = engine.get_telemetry()
    assert tel.uptime_sec > 1.0
    assert tel.rf_connected is True
    assert tel.mic_connected is True
    assert tel.rf_windows_processed > 0
    assert tel.acoustic_chunks_processed > 0

    # 3. Test pause and resume
    engine.pause()
    assert engine.is_paused is True
    time.sleep(0.2)
    engine.resume()
    assert engine.is_paused is False

    # 4. Graceful stop
    engine.stop()
    assert engine.is_running is False

    # 5. Verify system events log created
    sys_log_path = tmp_path / "data" / "events" / "system_events.jsonl"
    assert sys_log_path.exists()
    content = sys_log_path.read_text()
    assert "EngineStarted" in content
    assert "EngineStopped" in content
