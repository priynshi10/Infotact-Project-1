"""
AetherHound FFT Engine Module
High-performance windowed Fast Fourier Transforms, Power Spectral Density (PSD),
Welch estimations, and calibrated dB conversions.
"""

from typing import Tuple, Union
import numpy as np
from scipy import signal


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
