"""
Unit Tests for AetherHound Sensor Ingestion Layer.
"""

import numpy as np
import pytest
from aetherhound.sensors.audio_receiver import AudioReceiver
from aetherhound.sensors.sdr_receiver import SDRReceiver
from aetherhound.sensors.emulator import AirGapEnvironmentEmulator

def test_audio_receiver_stream():
    receiver = AudioReceiver()
    receiver.start()
    assert receiver.is_running
    chunk = receiver.read_chunk(1024)
    assert chunk.shape == (receiver.channels, 1024)
    assert chunk.dtype == np.float32
    meta = receiver.get_metadata()
    assert meta["channels"] == receiver.channels
    receiver.stop()
    assert not receiver.is_running

def test_sdr_receiver_iq_stream():
    sdr = SDRReceiver()
    sdr.start()
    assert sdr.is_running
    iq_chunk = sdr.read_chunk(1024)
    assert len(iq_chunk) == 1024
    assert np.iscomplexobj(iq_chunk)
    meta = sdr.get_metadata()
    assert meta["center_freq_mhz"] > 0
    sdr.stop()
    assert not sdr.is_running

def test_airgap_emulator_injection():
    emulator = AirGapEnvironmentEmulator()
    # Baseline
    audio_base, rssi_base = emulator.generate_multichannel_acoustic(2048)
    assert audio_base.shape[0] == len(emulator.config.layout.sensor_nodes)
    assert len(rssi_base) == len(emulator.config.layout.sensor_nodes)

    # Injected Fansmitter
    emulator.set_fansmitter_state(active=True, rack="Rack-Beta", freq_hz=2100.0)
    audio_atk, rssi_atk = emulator.generate_multichannel_acoustic(2048)
    assert audio_atk.shape == audio_base.shape
    # Attack increases energy at least at one sensor
    assert np.max(audio_atk) != np.max(audio_base)

    # SDR RF emulation
    rf_iq = emulator.generate_rf_iq(1024)
    assert len(rf_iq) == 1024
    assert np.iscomplexobj(rf_iq)
