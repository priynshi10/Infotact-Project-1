import numpy as np
import pytest
import soundfile as sf

from aetherhound.dsp.fft_engine import (
    compute_real_fft,
    fir_lowpass_filter,
)
from aetherhound.dsp.flowgraph import SignalProcessingFlowgraph
from aetherhound.dsp.spectrogram import (
    RollingWaterfallBuffer,
)
from aetherhound.hardware.acoustic_capture import (
    AcousticCaptureDevice,
    AudioChunk,
)
from aetherhound.hardware.rf_capture import IQSampleWindow
from aetherhound.hardware.config import AcousticConfig, RFConfig
from aetherhound.core.realtime_engine import RealtimeEngine
from aetherhound.interface.live_monitor import LiveMonitorInterface


def test_fir_lowpass_reduces_out_of_band_and_handles_empty():
    sr = 8000.0
    t = np.arange(sr) / sr
    samples = np.sin(2 * np.pi * 500 * t) + 0.5 * np.sin(2 * np.pi * 3000 * t)
    filtered = fir_lowpass_filter(samples, sr, 1000.0, 101)
    segment = filtered[500:]
    spectrum = np.abs(np.fft.rfft(segment))
    freqs = np.fft.rfftfreq(len(segment), d=1.0 / sr)
    in_band = spectrum[int(np.argmin(np.abs(freqs - 500)))]
    out_band = spectrum[int(np.argmin(np.abs(freqs - 3000)))]
    assert in_band > 2.0 * out_band
    assert fir_lowpass_filter(np.array([]), sr, 1000.0).size == 0


def test_real_fft_frequency_bin_accuracy():
    sr = 8000.0
    t = np.arange(4096) / sr
    samples = np.sin(2 * np.pi * 1000 * t)
    freqs, db = compute_real_fft(samples, 4096, sr)
    peak = freqs[int(np.argmax(db))]
    assert abs(peak - 1000.0) <= sr / 4096


def test_complex_fft_and_flowgraph_fallback():
    sr = 2_048_000.0
    t = np.arange(4096) / sr
    iq = np.exp(2j * np.pi * 100_000 * t).astype(np.complex64)
    flowgraph = SignalProcessingFlowgraph("rf", sr, cutoff_hz=400_000, fft_size=1024)
    result = flowgraph.process(iq)
    assert result.mode == "PYTHON NUMPY/SCIPY FALLBACK"
    assert np.iscomplexobj(result.filtered_samples)
    assert result.spectrum_db.size == 1024
    assert result.spectrogram_db.shape[0] > 0


def test_flowgraph_empty_input_is_safe():
    result = SignalProcessingFlowgraph("acoustic", 44100).process(np.array([]))
    assert result.filtered_samples.size == 0
    assert result.warning is not None


def test_synthetic_acoustic_and_rf_flowgraph_sources():
    acoustic = SignalProcessingFlowgraph("acoustic", 44100).synthetic_source(0.1, 0.01)
    rf = SignalProcessingFlowgraph("rf", 2_048_000).synthetic_source(0.001, 0.02)
    assert acoustic.ndim == 1 and np.isrealobj(acoustic)
    assert len(acoustic) > 0
    assert np.iscomplexobj(rf) and len(rf) > 0


def test_capture_synthetic_generators_change_samples():
    audio_cfg = AcousticConfig(sample_rate_hz=16000, chunk_size=256)
    audio = AcousticCaptureDevice(audio_cfg, synthetic_mode=True)
    audio._is_running.set()
    import threading
    audio._synthetic_thread = threading.Thread(target=audio._synthetic_audio_loop)
    audio._synthetic_thread.start()
    chunk1 = audio.get_chunk(timeout=1)
    chunk2 = audio.get_chunk(timeout=1)
    audio.stop()
    assert chunk1 is not None and chunk2 is not None
    assert not np.array_equal(chunk1.samples, chunk2.samples)


def test_rolling_waterfall_push_and_thread_safe_update():
    waterfall = RollingWaterfallBuffer(max_rows=3, num_bins=8)
    for index in range(5):
        waterfall.push_spectrum(
            np.full(8, float(index)),
            np.arange(8),
            float(index),
        )
    matrix, freqs, timestamps = waterfall.get_waterfall_matrix()
    assert matrix.shape == (3, 8)
    assert len(freqs) == 8
    assert list(timestamps) == [2.0, 3.0, 4.0]


def test_invalid_stft_and_processor_inputs_are_safe(tmp_path):
    from aetherhound.dsp.spectrogram import compute_stft_spectrogram

    with pytest.raises(ValueError, match="At least two"):
        compute_stft_spectrogram(np.array([]), 8000)

    rf = RealtimeEngine(
        synthetic_rf=True,
        synthetic_audio=True,
        data_dir=str(tmp_path / "data"),
    )
    empty = IQSampleWindow(
        samples=np.array([], dtype=np.complex64),
        timestamp=1.0,
        center_freq_hz=433920000.0,
        sample_rate_hz=2048000.0,
        is_synthetic=True,
        source_type="SYNTHETIC_SIMULATION",
    )
    processed = rf.process_external_rf_window(empty)
    assert processed.spectrum_db.size == rf.config.rf.fft_size


def test_cli_file_loader_integrates_wav_with_acoustic_engine(tmp_path):
    wav_path = tmp_path / "captured.wav"
    sr = 16000
    t = np.arange(sr) / sr
    sf.write(wav_path, np.sin(2 * np.pi * 1000 * t).astype(np.float32), sr)

    engine = RealtimeEngine(
        synthetic_rf=False,
        synthetic_audio=False,
        data_dir=str(tmp_path / "data"),
    )
    monitor = LiveMonitorInterface(
        engine,
        operating_mode="FILE",
        signal_type="RF",
        input_path=str(wav_path),
    )
    frames = monitor._load_file_frames(str(wav_path))
    assert monitor.signal_type == "ACOUSTIC"
    assert len(frames) > 0
    processed = engine.process_external_acoustic_chunk(frames[0])
    assert processed.filtered_samples.ndim == 1
