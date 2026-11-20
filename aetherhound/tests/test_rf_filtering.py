import numpy as np

from aetherhound.dsp.rf_processor import RFProcessor
from aetherhound.hardware.config import RFConfig
from aetherhound.hardware.rf_capture import IQSampleWindow


def test_rf_filter_preserves_in_band_and_reduces_out_of_band():
    sample_rate = 2_048_000.0
    sample_count = 16384
    t = np.arange(sample_count) / sample_rate

    in_band = np.exp(2j * np.pi * 100_000 * t)
    out_of_band = np.exp(2j * np.pi * 700_000 * t)

    original_iq = (in_band + out_of_band).astype(np.complex64)
    original_copy = original_iq.copy()

    config = RFConfig(
        sample_rate_hz=sample_rate,
        center_freq_hz=433_920_000.0,
        fft_size=2048,
        rf_filter_enabled=True,
        rf_filter_cutoff_hz=400_000.0,
        rf_filter_taps=101,
    )

    processor = RFProcessor(config)

    window = IQSampleWindow(
        samples=original_iq,
        timestamp=100.0,
        center_freq_hz=config.center_freq_hz,
        sample_rate_hz=sample_rate,
        window_id=1,
    )

    processor.process_window(window)

    filtered = processor.latest_filtered_iq

    assert filtered is not None
    assert np.array_equal(original_iq, original_copy)
    assert np.array_equal(processor.latest_raw_iq, original_copy)

    # Ignore filter startup transient when measuring signal amplitudes.
    original_segment = original_iq[2000:]
    filtered_segment = filtered[2000:]

    n = len(filtered_segment)
    spectrum = np.fft.fft(filtered_segment)

    frequencies = np.fft.fftfreq(n, d=1 / sample_rate)

    in_band_index = np.argmin(np.abs(frequencies - 100_000))
    out_band_index = np.argmin(np.abs(frequencies - 700_000))

    filtered_in_band = abs(spectrum[in_band_index]) / n
    filtered_out_band = abs(spectrum[out_band_index]) / n

    assert filtered_in_band > 0.8
    assert filtered_out_band < 0.1
