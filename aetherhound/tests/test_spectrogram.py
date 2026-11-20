import numpy as np
import pytest

from aetherhound.dsp.spectrogram import compute_stft_spectrogram


def test_acoustic_stft_detects_known_frequency():
    sample_rate = 8000
    t = np.arange(8000) / sample_rate
    samples = np.sin(2 * np.pi * 1000 * t)

    frequencies, times, spectrogram = compute_stft_spectrogram(
        samples, sample_rate, nperseg=512, noverlap=256
    )

    detected_frequency = frequencies[
        np.argmax(np.mean(spectrogram, axis=1))
    ]

    assert spectrogram.shape == (len(frequencies), len(times))
    assert len(times) > 1
    assert abs(detected_frequency - 1000) <= sample_rate / 512


def test_complex_iq_stft_detects_known_frequency():
    sample_rate = 2_000_000
    t = np.arange(16384) / sample_rate
    samples = np.exp(2j * np.pi * 250_000 * t)

    frequencies, times, spectrogram = compute_stft_spectrogram(
        samples, sample_rate, nperseg=1024, noverlap=512
    )

    detected_frequency = frequencies[
        np.argmax(np.mean(spectrogram, axis=1))
    ]

    assert len(frequencies) == 1024
    assert spectrogram.shape == (len(frequencies), len(times))
    assert abs(detected_frequency - 250_000) <= sample_rate / 1024


def test_stft_handles_short_signal():
    samples = np.sin(2 * np.pi * 100 * np.arange(32) / 1000)

    frequencies, times, spectrogram = compute_stft_spectrogram(
        samples, 1000, nperseg=512
    )

    assert len(frequencies) > 0
    assert len(times) > 0
    assert spectrogram.shape == (len(frequencies), len(times))


def test_stft_rejects_invalid_sample_rate():
    samples = np.ones(100)

    with pytest.raises(ValueError, match="Sample rate must be positive"):
        compute_stft_spectrogram(samples, 0)


def test_stft_rejects_multidimensional_input():
    samples = np.ones((10, 10))

    with pytest.raises(ValueError, match="one-dimensional"):
        compute_stft_spectrogram(samples, 1000)
