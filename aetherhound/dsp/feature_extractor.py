"""
AetherHound Feature Extractor Module
Extracts time-domain, spectral-domain, and envelope features
for RF and acoustic covert channel analysis.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np
from scipy import signal


@dataclass
class AcousticFeatures:
    """Extracted acoustic feature vector for a processing window."""
    rms_energy: float
    peak_amplitude: float
    dominant_frequency_hz: float
    spectral_centroid_hz: float
    spectral_bandwidth_hz: float
    zero_crossing_rate: float
    periodicity_score: float
    snr_estimate_db: float


def compute_rms_energy(audio: np.ndarray) -> float:
    """Compute Root-Mean-Square energy of audio samples."""
    if len(audio) == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio))))


def compute_peak_amplitude(audio: np.ndarray) -> float:
    """Compute maximum absolute peak amplitude."""
    if len(audio) == 0:
        return 0.0
    return float(np.max(np.abs(audio)))


def compute_zero_crossing_rate(audio: np.ndarray) -> float:
    """Compute normalized zero crossing rate (crossings per sample)."""
    if len(audio) < 2:
        return 0.0
    signs = np.sign(audio)
    # Replace zeros with 1 to avoid false double crossings
    signs[signs == 0] = 1
    crossings = np.sum(np.abs(np.diff(signs))) / 2.0
    return float(crossings / (len(audio) - 1))


def compute_spectral_centroid_and_bandwidth(
    magnitudes: np.ndarray,
    frequencies_hz: np.ndarray,
) -> Tuple[float, float]:
    """
    Compute Spectral Centroid (center of mass of spectrum)
    and Spectral Bandwidth (spectral spread).
    """
    total_power = np.sum(magnitudes)
    if total_power <= 1e-12:
        return 0.0, 0.0

    # Spectral centroid: sum(f * M) / sum(M)
    centroid = float(np.sum(frequencies_hz * magnitudes) / total_power)

    # Spectral bandwidth: sqrt( sum( (f - centroid)^2 * M ) / sum(M) )
    variance = np.sum(np.square(frequencies_hz - centroid) * magnitudes) / total_power
    bandwidth = float(np.sqrt(np.maximum(variance, 0.0)))

    return centroid, bandwidth


class StreamingEnvelopeFollower:
    """
    Causal single-pole attack/release envelope detector that maintains state
    continuously across streaming audio chunks.
    """

    def __init__(
        self,
        sample_rate_hz: int,
        attack_time_sec: float = 0.015,
        release_time_sec: float = 0.040,
    ):
        self.sample_rate_hz = sample_rate_hz
        self.attack_coeff = float(np.exp(-1.0 / max(1.0, sample_rate_hz * attack_time_sec)))
        self.release_coeff = float(np.exp(-1.0 / max(1.0, sample_rate_hz * release_time_sec)))
        self.current_env = 0.0

    def process(self, audio: np.ndarray) -> np.ndarray:
        rect = np.abs(audio)
        n = len(rect)
        if n == 0:
            return np.zeros(0, dtype=np.float32)

        # Warm start current_env on very first frame to avoid false onset edge from zero
        if self.current_env == 0.0 and n > 0:
            self.current_env = float(np.mean(rect[:min(n, 64)]))

        env = np.zeros(n, dtype=np.float32)
        curr = self.current_env
        att = self.attack_coeff
        rel = self.release_coeff

        for i in range(n):
            val = rect[i]
            if val > curr:
                curr = att * curr + (1.0 - att) * val
            else:
                curr = rel * curr + (1.0 - rel) * val
            env[i] = curr

        self.current_env = curr
        return env


def extract_signal_envelope(
    audio: np.ndarray,
    sample_rate_hz: int,
    cutoff_hz: float = 30.0,
) -> np.ndarray:
    """
    Extract smooth signal amplitude envelope using Hilbert transform or
    rectification + low-pass Butterworth filter.
    """
    if len(audio) < 16:
        return np.abs(audio)

    # Full-wave rectification
    rectified = np.abs(audio)

    # Low-pass filter designed for Morse keying rate (typically 5 - 30 Hz)
    nyquist = 0.5 * sample_rate_hz
    norm_cutoff = min(0.45, max(0.001, cutoff_hz / nyquist))
    try:
        b, a = signal.butter(2, norm_cutoff, btype="low")
        envelope = signal.filtfilt(b, a, rectified)
        return np.maximum(envelope, 0.0).astype(np.float32)
    except Exception:
        # Fallback to rolling boxcar smoothing if filtfilt fails
        window_len = max(5, int(sample_rate_hz * 0.02))
        kernel = np.ones(window_len) / window_len
        smoothed = np.convolve(rectified, kernel, mode="same")
        return smoothed.astype(np.float32)


def compute_periodicity_score(
    envelope: np.ndarray,
    min_lag_samples: int = 10,
    max_lag_samples: Optional[int] = None,
) -> float:
    """
    Compute normalized autocorrelation peak in the signal envelope
    to identify repetitive periodic pulsed activity (such as fan modulation).
    Returns score in [0.0, 1.0].
    """
    n = len(envelope)
    if n < min_lag_samples * 2:
        return 0.0

    centered = envelope - np.mean(envelope)
    var = np.sum(np.square(centered))
    if var <= 1e-12:
        return 0.0

    corr = signal.correlate(centered, centered, mode="full")[n - 1 :]
    norm_corr = corr / corr[0]

    max_lag = max_lag_samples if max_lag_samples is not None else n // 2
    if max_lag <= min_lag_samples:
        return 0.0

    valid_region = norm_corr[min_lag_samples:max_lag]
    if len(valid_region) == 0:
        return 0.0

    peak_score = float(np.max(valid_region))
    return float(np.clip(peak_score, 0.0, 1.0))


def extract_acoustic_features(
    audio: np.ndarray,
    sample_rate_hz: int,
    fft_size: int = 2048,
) -> AcousticFeatures:
    """
    Extract complete acoustic feature vector from an audio chunk.
    """
    rms = compute_rms_energy(audio)
    peak = compute_peak_amplitude(audio)
    zcr = compute_zero_crossing_rate(audio)

    # Spectral analysis
    n = len(audio)
    slice_len = min(n, fft_size)
    windowed = audio[:slice_len] * np.hanning(slice_len)
    fft_vals = np.fft.rfft(windowed, n=fft_size)
    magnitudes = np.abs(fft_vals)
    freqs = np.fft.rfftfreq(fft_size, d=1.0 / sample_rate_hz)

    # Dominant frequency
    if len(magnitudes) > 0:
        peak_idx = int(np.argmax(magnitudes))
        dominant_freq = float(freqs[peak_idx])
    else:
        dominant_freq = 0.0

    centroid, bandwidth = compute_spectral_centroid_and_bandwidth(magnitudes, freqs)

    # Envelope & Periodicity
    envelope = extract_signal_envelope(audio, sample_rate_hz)
    periodicity = compute_periodicity_score(envelope)

    # SNR estimate: peak magnitude vs median magnitude
    med_mag = float(np.median(magnitudes))
    if med_mag > 1e-12:
        max_mag = float(np.max(magnitudes))
        snr_est = float(20.0 * np.log10(max_mag / med_mag))
    else:
        snr_est = 0.0

    return AcousticFeatures(
        rms_energy=rms,
        peak_amplitude=peak,
        dominant_frequency_hz=dominant_freq,
        spectral_centroid_hz=centroid,
        spectral_bandwidth_hz=bandwidth,
        zero_crossing_rate=zcr,
        periodicity_score=periodicity,
        snr_estimate_db=snr_est,
    )
