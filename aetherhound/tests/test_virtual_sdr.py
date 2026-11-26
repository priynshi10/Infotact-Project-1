import sys
import types

import numpy as np
import pytest
from pathlib import Path

from aetherhound.hardware.virtual_sdr import VirtualSDR, VirtualSDRConfig
from aetherhound.dsp.flowgraph import SignalProcessingFlowgraph


def test_virtual_sdr_generates_finite_iq_components():
    config = VirtualSDRConfig(chunk_size=4096, seed=123)
    receiver = VirtualSDR(config, components_hz=(100_000.0, -250_000.0))
    block = receiver.generate_block()
    assert block.dtype == np.complex64
    assert block.shape == (4096,)
    assert np.all(np.isfinite(block))
    assert receiver.read_window().source_type == "VIRTUAL_SDR"


def test_virtual_sdr_stream_is_bounded_and_stops():
    config = VirtualSDRConfig(chunk_size=256, seed=123)
    receiver = VirtualSDR(config, queue_size=2)
    assert receiver.start()
    window = receiver.get_window(timeout=1.0)
    assert window is not None
    assert window.samples.size == 256
    assert window.source_type == "VIRTUAL_SDR"
    receiver.stop()
    assert not receiver.is_running


def test_virtual_sdr_npy_and_npz_file_playback(tmp_path):
    iq = (np.exp(2j * np.pi * np.arange(128) / 16)).astype(np.complex64)
    npy_path = tmp_path / "iq.npy"
    np.save(npy_path, iq)
    receiver = VirtualSDR(VirtualSDRConfig(chunk_size=128), loop_file=True)
    loaded = receiver.load_iq_file(str(npy_path))
    assert np.array_equal(loaded, iq)
    assert np.array_equal(receiver.read_window().samples, iq)

    npz_path = tmp_path / "iq.npz"
    np.savez(npz_path, iq=iq)
    receiver.load_iq_file(str(npz_path))


def test_virtual_sdr_rejects_invalid_iq_file(tmp_path):
    npy_path = tmp_path / "bad.npy"
    np.save(npy_path, np.ones(128))
    receiver = VirtualSDR(VirtualSDRConfig(chunk_size=128))
    with pytest.raises(ValueError, match="complex"):
        receiver.load_iq_file(str(npy_path))


def test_virtual_sdr_dsp_integration():
    receiver = VirtualSDR(
        VirtualSDRConfig(chunk_size=4096, sample_rate_hz=800_000.0),
        components_hz=(50_000.0,),
    )
    result = receiver.read_window()
    flowgraph = SignalProcessingFlowgraph(
        "rf", 800_000.0, cutoff_hz=200_000.0, fft_size=1024,
    )
    output = flowgraph.process(result.samples)
    assert np.all(np.isfinite(output.spectrum_db))
    assert output.spectrogram_db.shape[0] > 0


def test_gnuradio_mock_lifecycle(monkeypatch):
    class MockBlock:
        def start(self):
            self.started = True
        def stop(self):
            self.started = False
        def wait(self):
            self.waited = True
        def connect(self, *args):
            pass

    monkeypatch.setattr(
        "aetherhound.dsp.flowgraph.find_spec",
        lambda name: object(),
    )
    fake_gr = types.ModuleType("gnuradio.gr")
    fake_gr.top_block = lambda name: MockBlock()
    fake_gr_module = types.ModuleType("gnuradio")
    fake_blocks = types.SimpleNamespace(
        vector_source_c=lambda *args: object(),
        vector_sink_c=lambda: object(),
    )
    fake_filter = types.SimpleNamespace(
        firdes=types.SimpleNamespace(low_pass=lambda *args: [1.0]),
        fir_filter_ccf=lambda *args: object(),
    )

    monkeypatch.setitem(sys.modules, "gnuradio", fake_gr_module)
    monkeypatch.setitem(sys.modules, "gnuradio.gr", fake_gr)
    fake_gr_module.blocks = fake_blocks
    fake_gr_module.filter = fake_filter

    flowgraph = SignalProcessingFlowgraph(
        "rf", 2_048_000.0, cutoff_hz=400_000.0, backend="gnuradio",
    )
    selected = flowgraph.initialize()
    assert "GNU RADIO" in selected
    flowgraph.start()
    flowgraph.wait()
    flowgraph.stop()


def test_arm64_static_compatibility_check():
    from aetherhound.scripts.arm64_compat import compatibility_report
    report = compatibility_report()
    assert "os" in report
    assert "is_arm64" in report
    assert "numpy" in report


def test_deployment_service_and_scripts_exist():
    root = Path(__file__).resolve().parents[2]
    assert (root / "deploy" / "aetherhound.service").is_file()
    assert (root / "deploy" / "aetherhound-start.sh").is_file()
    assert (root / "deploy" / "aetherhound-stop.sh").is_file()
