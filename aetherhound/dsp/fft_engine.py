"""
AetherHound FFT Engine Module
High-performance windowed Fast Fourier Transforms, Power Spectral Density (PSD),
Welch estimations, and calibrated dB conversions.
"""

from typing import Tuple, Union
import numpy as np
from scipy import signal


def fir_lowpass_filter(
    samples: np.ndarray,
    sample_rate_hz: float,
    cutoff_hz: float,
    numtaps: int = 101,
) -> np.ndarray:
    """Apply a linear-phase FIR low-pass filter to real or complex samples."""
    values = np.asarray(samples)
    if values.size == 0:
        return values.copy()
    if not np.issubdtype(values.dtype, np.number):
        raise ValueError("Samples must contain numeric values")
    if not np.isfinite(sample_rate_hz) or sample_rate_hz <= 0:
        raise ValueError("Sample rate must be positive")
    if not np.isfinite(cutoff_hz) or cutoff_hz <= 0:
        raise ValueError("Cutoff frequency must be positive")

    cutoff_hz = min(float(cutoff_hz), float(sample_rate_hz) * 0.45)
    taps = max(3, min(int(numtaps), values.size))
    if taps % 2 == 0:
        taps -= 1
    if taps < 3:
        return values.copy()

    coefficients = signal.firwin(taps, cutoff_hz, fs=float(sample_rate_hz), window="hamming")
    return signal.lfilter(coefficients, [1.0], values)


def compute_real_fft(
    samples: np.ndarray,
    fft_size: int,
    sample_rate_hz: float,
    window_type: str = "hann",
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute a real-signal, one-sided FFT and return frequencies plus dB magnitude."""
    values = np.asarray(samples)
    if values.size == 0:
        return np.array([], dtype=float), np.array([], dtype=float)
    if values.ndim != 1:
        raise ValueError("Samples must be a one-dimensional array")
    if not np.isfinite(sample_rate_hz) or sample_rate_hz <= 0:
        raise ValueError("Sample rate must be positive")
    if fft_size < 2:
        raise ValueError("FFT size must be at least 2")

    fft_size = int(fft_size)
    frame = values[:fft_size] if values.size >= fft_size else np.pad(values, (0, fft_size - values.size))
    windowed, coherent_gain = apply_window(np.asarray(frame, dtype=float), window_type)
    spectrum = np.fft.rfft(windowed) / (fft_size * coherent_gain)
    frequencies = np.fft.rfftfreq(fft_size, d=1.0 / float(sample_rate_hz))
    magnitude_db = 20.0 * np.log10(np.maximum(np.abs(spectrum), 1e-12))
    return frequencies, magnitude_db


def apply_window(
    samples: np.ndarray,
    window_type: str = "hann",
) -> Tuple[np.ndarray, float]:
    """
    Apply a window function to samples and compute coherent gain compensation.
    Supported windows: hann, hamming, blackmanharris, flattop, rect.
    """
    n = len(samples)
    if window_type == "hann":
        win = np.hanning(n)
    elif window_type == "hamming":
        win = np.hamming(n)
    elif window_type == "blackmanharris":
        win = signal.windows.blackmanharris(n)
    elif window_type == "flattop":
        win = signal.windows.flattop(n)
    elif window_type == "rect":
        win = np.ones(n)
    else:
        win = np.hanning(n)

    # Coherent gain normalization factor
    coherent_gain = float(np.sum(win) / n)
    if coherent_gain == 0.0:
        coherent_gain = 1.0

    return samples * win, coherent_gain


def compute_complex_fft(
    iq_samples: np.ndarray,
    fft_size: int,
    window_type: str = "hann",
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute centered complex FFT for IQ samples.
    Returns (freqs_normalized, complex_spectrum_shifted).
    """
    iq_samples = np.asarray(iq_samples)
    if iq_samples.size == 0:
        return np.array([], dtype=float), np.array([], dtype=complex)
    if iq_samples.ndim != 1:
        raise ValueError("IQ samples must be a one-dimensional array")
    n = len(iq_samples)
    if n > fft_size:
        # Use first fft_size samples or segment average
        sample_slice = iq_samples[:fft_size]
    elif n < fft_size:
        sample_slice = np.pad(iq_samples, (0, fft_size - n), mode="constant")
    else:
        sample_slice = iq_samples

    windowed, coherent_gain = apply_window(sample_slice, window_type)
    # FFT and shift zero-frequency to center
    fft_raw = np.fft.fft(windowed, n=fft_size) / (fft_size * coherent_gain)
    fft_shifted = np.fft.fftshift(fft_raw)
    freqs_norm = np.fft.fftshift(np.fft.fftfreq(fft_size, d=1.0))

    return freqs_norm, fft_shifted


def compute_power_spectrum_db(
    iq_samples: np.ndarray,
    fft_size: int,
    sample_rate_hz: float,
    center_freq_hz: float,
    window_type: str = "hann",
    reference_power: float = 1.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute centered Power Spectral Density in dBFS / dB relative to reference.
    Returns:
        (actual_frequencies_hz, power_spectrum_db)
    """
    freqs_norm, fft_shifted = compute_complex_fft(iq_samples, fft_size, window_type)
    # Convert normalized frequencies [-0.5, 0.5) to actual RF Hz
    actual_frequencies_hz = center_freq_hz + (freqs_norm * sample_rate_hz)

    # Power in linear scale: |X|^2
    power_linear = np.real(fft_shifted * np.conj(fft_shifted))
    # Avoid log of zero with floor at 1e-18 (-180 dB)
    power_linear = np.maximum(power_linear, 1e-18)
    power_db = 10.0 * np.log10(power_linear / reference_power)

    return actual_frequencies_hz, power_db


def compute_welch_psd(
    samples: np.ndarray,
    sample_rate_hz: float,
    center_freq_hz: float = 0.0,
    nperseg: int = 1024,
    window_type: str = "hann",
    is_complex: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute averaged Welch Power Spectral Density.
    """
    return_onesided = not is_complex
    f, psd = signal.welch(
        samples,
        fs=sample_rate_hz,
        window=window_type,
        nperseg=min(nperseg, len(samples)),
        return_onesided=return_onesided,
        scaling="density",
    )
    if is_complex:
        f = np.fft.fftshift(f)
        psd = np.fft.fftshift(psd)
        actual_f = center_freq_hz + f
    else:
        actual_f = f

    psd_safe = np.maximum(psd, 1e-18)
    psd_db = 10.0 * np.log10(psd_safe)
    return actual_f, psd_db
