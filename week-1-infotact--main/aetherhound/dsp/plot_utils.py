"""
AetherHound Signal Visualization & Plotting Utility with Full Data Provenance
Generates publication-quality Matplotlib figures with cryptographic metadata,
verifiable raw sample bindings, and explicit Live Hardware vs Synthetic labelling.
"""

from datetime import datetime, timezone
import json
import os
import time
from typing import Optional, Tuple, Union

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless / server environments
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf

from aetherhound.dsp.provenance import (
    EvidenceProvenance,
    SourceModeType,
    compute_array_sha256,
    compute_file_sha256,
    save_provenance_metadata,
)


def _draw_provenance_header(
    fig,
    source_mode: SourceModeType,
    sensor_id: str,
    timestamp_iso: str,
    raw_sha256: str,
    extra_info: str = "",
):
    """Draw a standardized, immutable provenance header on top of the Matplotlib figure."""
    bg_color = "#004d40" if source_mode == "LIVE HARDWARE" else (
        "#263238" if source_mode == "SYNTHETIC SIMULATION" else "#1a237e"
    )
    border_color = "#00e676" if source_mode == "LIVE HARDWARE" else (
        "#78909c" if source_mode == "SYNTHETIC SIMULATION" else "#536dfe"
    )
    tag_color = "#69f0ae" if source_mode == "LIVE HARDWARE" else (
        "#b0bec5" if source_mode == "SYNTHETIC SIMULATION" else "#8c9eff"
    )

    header_text = (
        f"PROVENANCE: [{source_mode}] | SENSOR: {sensor_id} | "
        f"TIME: {timestamp_iso} | SHA256: {raw_sha256[:12]}..."
    )
    if extra_info:
        header_text += f" | {extra_info}"

    fig.text(
        0.5,
        0.985,
        header_text,
        ha="center",
        va="top",
        fontsize=8,
        fontfamily="monospace",
        fontweight="bold",
        color=tag_color,
        bbox=dict(
            boxstyle="square,pad=0.4",
            facecolor=bg_color,
            edgecolor=border_color,
            linewidth=1.2,
        ),
    )


def save_rf_spectrum_plot(
    frequencies_hz: np.ndarray,
    spectrum_db: np.ndarray,
    noise_floor_db: float,
    output_path: str,
    raw_iq_samples: Optional[np.ndarray] = None,
    source_mode: SourceModeType = "SYNTHETIC SIMULATION",
    sensor_id: str = "SDR-01",
    center_freq_hz: float = 433_920_000.0,
    sample_rate_hz: float = 2_048_000.0,
    timestamp_epoch: Optional[float] = None,
    title: str = "AetherHound Calibrated RF Spectrum",
    highlight_peak_hz: Optional[float] = None,
    peak_power_db: Optional[float] = None,
) -> Tuple[str, EvidenceProvenance]:
    """
    Save calibrated RF spectrum figure accompanied by raw IQ dump and provenance JSON.
    """
    t_epoch = timestamp_epoch or time.time()
    t_iso = datetime.fromtimestamp(t_epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    base_name = os.path.splitext(os.path.basename(output_path))[0]
    data_root = os.path.abspath(os.path.join(os.path.dirname(output_path), "..", ".."))

    # 1. Save raw IQ array if supplied
    raw_dir = os.path.join(data_root, "rf", "raw")
    os.makedirs(raw_dir, exist_ok=True)
    raw_path = os.path.join(raw_dir, f"{base_name}_iq.npy")

    if raw_iq_samples is not None:
        np.save(raw_path, raw_iq_samples)
        raw_hash = compute_array_sha256(raw_iq_samples)
        sample_count = len(raw_iq_samples)
    else:
        # Fallback to hashing spectrum array
        np.save(raw_path, spectrum_db)
        raw_hash = compute_array_sha256(spectrum_db)
        sample_count = len(spectrum_db)

    duration_sec = sample_count / sample_rate_hz if sample_rate_hz > 0 else 0.0

    # 2. Render Matplotlib Figure
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=120)
    plt.subplots_adjust(top=0.90, bottom=0.12, left=0.10, right=0.95)

    freqs_mhz = frequencies_hz / 1e6
    line_color = "#00bcd4" if source_mode == "LIVE HARDWARE" else "#00acc1"
    ax.plot(freqs_mhz, spectrum_db, color=line_color, linewidth=1.0, label="Calibrated Power Spectrum (FFT)")
    ax.axhline(
        noise_floor_db,
        color="#ff9800",
        linestyle="--",
        linewidth=1.2,
        label=f"Noise Floor (MAD: {noise_floor_db:.1f} dBFS)",
    )

    if highlight_peak_hz is not None:
        dev = (peak_power_db - noise_floor_db) if peak_power_db is not None else 0.0
        label_txt = f"Detected Anomaly: {highlight_peak_hz / 1e6:.3f} MHz"
        if dev > 0:
            label_txt += f" (+{dev:.1f} dB)"
        ax.axvline(highlight_peak_hz / 1e6, color="#f44336", linestyle=":", linewidth=1.5, label=label_txt)

    ax.set_title(title, fontsize=11, fontweight="bold", pad=12)
    ax.set_xlabel("RF Frequency (MHz)", fontsize=10)
    ax.set_ylabel("Power Spectral Density (dBFS)", fontsize=10)
    ax.set_ylim(-130, 0)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right", fontsize=8)

    # Provenance Banner
    _draw_provenance_header(
        fig,
        source_mode=source_mode,
        sensor_id=sensor_id,
        timestamp_iso=t_iso,
        raw_sha256=raw_hash,
        extra_info=f"Fc: {center_freq_hz / 1e6:.3f} MHz | Fs: {sample_rate_hz / 1e6:.3f} Msps | N: {sample_count}",
    )

    fig.savefig(output_path)
    plt.close(fig)

    # Mirror to public/data/ directory for Vite web preview
    try:
        public_plot = os.path.join("public", output_path) if not output_path.startswith("public") else output_path
        os.makedirs(os.path.dirname(os.path.abspath(public_plot)), exist_ok=True)
        import shutil
        shutil.copy2(output_path, public_plot)
    except Exception:
        pass

    # 3. Create Provenance Record
    meta = EvidenceProvenance(
        plot_path=output_path,
        source_mode=source_mode,
        sensor_id=sensor_id,
        capture_timestamp_iso=t_iso,
        capture_timestamp_epoch=t_epoch,
        sample_rate_hz=sample_rate_hz,
        center_freq_hz=center_freq_hz,
        recording_duration_sec=duration_sec,
        sample_count=sample_count,
        raw_data_path=raw_path,
        raw_data_sha256=raw_hash,
        device_verified=(source_mode == "LIVE HARDWARE"),
        detection_event_type="RF_SPECTRAL_ANOMALY" if highlight_peak_hz else None,
        metrics={
            "noise_floor_db": round(float(noise_floor_db), 2),
            "peak_freq_hz": round(float(highlight_peak_hz), 1) if highlight_peak_hz else 0.0,
            "peak_power_db": round(float(peak_power_db), 2) if peak_power_db else 0.0,
        },
        notes=f"Generated via AetherHound DSP FFT engine. Source validated as {source_mode}.",
    )

    # Save metadata adjacent to plot and in metadata dir
    json_path = os.path.splitext(output_path)[0] + ".json"
    save_provenance_metadata(meta, json_path)

    meta_dir = os.path.join(data_root, "rf", "metadata")
    os.makedirs(meta_dir, exist_ok=True)
    save_provenance_metadata(meta, os.path.join(meta_dir, f"{base_name}.json"))

    return output_path, meta


def save_acoustic_waveform_plot(
    times_sec: np.ndarray,
    audio: np.ndarray,
    envelope: np.ndarray,
    output_path: str,
    source_mode: SourceModeType = "SYNTHETIC SIMULATION",
    sensor_id: str = "MIC-01",
    sample_rate_hz: int = 44100,
    timestamp_epoch: Optional[float] = None,
    title: str = "AetherHound Acoustic Waveform & Pulse Envelope",
    target_morse: Optional[str] = "SOS",
    match_score: Optional[float] = None,
) -> Tuple[str, EvidenceProvenance]:
    """
    Save acoustic waveform and envelope plot from actual acquired microphone buffer.
    Guarantees raw WAV binding and cryptographic provenance.
    """
    t_epoch = timestamp_epoch or time.time()
    t_iso = datetime.fromtimestamp(t_epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    base_name = os.path.splitext(os.path.basename(output_path))[0]
    data_root = os.path.abspath(os.path.join(os.path.dirname(output_path), "..", ".."))

    # 1. Save raw audio capture in data/acoustic/raw/
    raw_dir = os.path.join(data_root, "acoustic", "raw")
    os.makedirs(raw_dir, exist_ok=True)
    raw_wav_path = os.path.join(raw_dir, f"{base_name}_capture.wav")
    sf.write(raw_wav_path, audio, sample_rate_hz)
    raw_hash = compute_file_sha256(raw_wav_path)

    sample_count = len(audio)
    duration_sec = sample_count / sample_rate_hz if sample_rate_hz > 0 else 0.0

    # 2. Render Matplotlib Figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True, dpi=120)
    plt.subplots_adjust(top=0.88, bottom=0.10, left=0.10, right=0.95, hspace=0.25)

    wave_color = "#4caf50" if source_mode == "LIVE HARDWARE" else "#66bb6a"
    ax1.plot(times_sec, audio, color=wave_color, linewidth=0.8, alpha=0.85)
    ax1.set_title("Acquired Audio Waveform (Input Buffer)", fontsize=10, fontweight="bold")
    ax1.set_ylabel("Amplitude", fontsize=9)
    ax1.grid(True, linestyle=":", alpha=0.6)

    ax2.plot(times_sec, envelope, color="#e91e63", linewidth=1.4, label="Streaming Causal Envelope")
    env_title = "Extracted Pulse Amplitude Envelope"
    if match_score:
        env_title += f" [Recognized {target_morse} | Score: {match_score * 100:.1f}%]"
    ax2.set_title(env_title, fontsize=10, fontweight="bold")
    ax2.set_xlabel("Time (seconds)", fontsize=9)
    ax2.set_ylabel("Envelope Power", fontsize=9)
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend(loc="upper right", fontsize=8)

    # Provenance Header
    _draw_provenance_header(
        fig,
        source_mode=source_mode,
        sensor_id=sensor_id,
        timestamp_iso=t_iso,
        raw_sha256=raw_hash,
        extra_info=f"Fs: {sample_rate_hz} Hz | Duration: {duration_sec:.2f}s | Samples: {sample_count}",
    )

    fig.savefig(output_path)
    plt.close(fig)

    # Mirror to public/data/ directory for Vite web preview
    try:
        public_plot = os.path.join("public", output_path) if not output_path.startswith("public") else output_path
        os.makedirs(os.path.dirname(os.path.abspath(public_plot)), exist_ok=True)
        import shutil
        shutil.copy2(output_path, public_plot)
    except Exception:
        pass

    # 3. Create Provenance Record
    meta = EvidenceProvenance(
        plot_path=output_path,
        source_mode=source_mode,
        sensor_id=sensor_id,
        capture_timestamp_iso=t_iso,
        capture_timestamp_epoch=t_epoch,
        sample_rate_hz=float(sample_rate_hz),
        center_freq_hz=None,
        recording_duration_sec=duration_sec,
        sample_count=sample_count,
        raw_data_path=raw_wav_path,
        raw_data_sha256=raw_hash,
        device_verified=(source_mode == "LIVE HARDWARE"),
        detection_event_type="ACOUSTIC_MORSE_PATTERN" if match_score else None,
        metrics={
            "duration_sec": round(duration_sec, 2),
            "match_score": round(match_score, 3) if match_score else 0.0,
            "target_pattern": target_morse or "",
        },
        notes=f"Captured from receiver stream. Authenticated as {source_mode}.",
    )

    json_path = os.path.splitext(output_path)[0] + ".json"
    save_provenance_metadata(meta, json_path)

    meta_dir = os.path.join(data_root, "acoustic", "metadata")
    os.makedirs(meta_dir, exist_ok=True)
    save_provenance_metadata(meta, os.path.join(meta_dir, f"{base_name}.json"))

    return output_path, meta


def save_fan_rpm_plot(
    times_sec: np.ndarray,
    rpms: np.ndarray,
    pulse_states: np.ndarray,
    output_path: str,
    source_mode: SourceModeType = "SYNTHETIC SIMULATION",
    sensor_id: str = "FAN-SIM-01",
    timestamp_epoch: Optional[float] = None,
    title: str = "AetherHound Benign Fan RPM Morse Trajectory",
    message: str = "SOS",
) -> Tuple[str, EvidenceProvenance]:
    """
    Save fan RPM trajectory plot. Explicitly labels software simulation vs tachometer measurements.
    """
    t_epoch = timestamp_epoch or time.time()
    t_iso = datetime.fromtimestamp(t_epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    base_name = os.path.splitext(os.path.basename(output_path))[0]
    data_root = os.path.abspath(os.path.join(os.path.dirname(output_path), "..", ".."))

    # Save CSV timeline
    csv_dir = os.path.join(data_root, "mock_fan", "rpm")
    os.makedirs(csv_dir, exist_ok=True)
    csv_path = os.path.join(csv_dir, f"{base_name}_timeline.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("time_sec,rpm,is_pulse\n")
        for t, r, p in zip(times_sec, rpms, pulse_states):
            f.write(f"{t:.4f},{r:.2f},{int(p)}\n")

    raw_hash = compute_file_sha256(csv_path)

    # Render figure
    fig, ax1 = plt.subplots(figsize=(10, 5.5), dpi=120)
    plt.subplots_adjust(top=0.88, bottom=0.12, left=0.10, right=0.90)

    color = "#2196f3"
    ax1.set_xlabel("Time (seconds)", fontsize=10)
    ax1.set_ylabel("Simulated Fan Speed (RPM)", color=color, fontsize=10)
    ax1.plot(times_sec, rpms, color=color, linewidth=2.0, label="Fan Trajectory (RPM)")
    ax1.tick_params(axis="y", labelcolor=color)

    ax2 = ax1.twinx()
    color2 = "#e91e63"
    ax2.set_ylabel("Morse Modulation State", color=color2, fontsize=10)
    ax2.fill_between(times_sec, 0, pulse_states.astype(int), color=color2, alpha=0.20, label="Transmitting Pulse (Dot/Dash)")
    ax2.set_ylim(-0.1, 1.5)
    ax2.set_yticks([0, 1])
    ax2.set_yticklabels(["Idle (Gap)", "Active (Pulse)"])
    ax2.tick_params(axis="y", labelcolor=color2)

    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.set_title(title, fontsize=11, fontweight="bold", pad=12)

    # Prominent simulation disclaimer banner on graph
    fig.text(
        0.5,
        0.02,
        "BENIGN SOFTWARE SIMULATION ONLY – NO PHYSICAL MOTHERBOARD/FAN MANIPULATION – TACHOMETER NOT ATTACHED",
        ha="center",
        va="bottom",
        fontsize=7,
        fontfamily="monospace",
        fontweight="bold",
        color="#ffa726",
    )

    _draw_provenance_header(
        fig,
        source_mode=source_mode,
        sensor_id=sensor_id,
        timestamp_iso=t_iso,
        raw_sha256=raw_hash,
        extra_info=f"Target: {message} | Base: 1200 RPM | High: 1800 RPM",
    )

    fig.savefig(output_path)
    plt.close(fig)

    # Mirror to public/data/ directory for Vite web preview
    try:
        public_plot = os.path.join("public", output_path) if not output_path.startswith("public") else output_path
        os.makedirs(os.path.dirname(os.path.abspath(public_plot)), exist_ok=True)
        import shutil
        shutil.copy2(output_path, public_plot)
    except Exception:
        pass

    meta = EvidenceProvenance(
        plot_path=output_path,
        source_mode=source_mode,
        sensor_id=sensor_id,
        capture_timestamp_iso=t_iso,
        capture_timestamp_epoch=t_epoch,
        sample_rate_hz=50.0,  # 50 Hz timeline rate
        center_freq_hz=None,
        recording_duration_sec=float(times_sec[-1]),
        sample_count=len(times_sec),
        raw_data_path=csv_path,
        raw_data_sha256=raw_hash,
        device_verified=False,
        detection_event_type="FAN_RPM_SIMULATION",
        metrics={
            "base_rpm": 1200.0,
            "low_rpm": 900.0,
            "high_rpm": 1800.0,
            "message": message,
        },
        notes="Software simulation of aerodynamic fan speed profile for laboratory detection calibration.",
    )

    json_path = os.path.splitext(output_path)[0] + ".json"
    save_provenance_metadata(meta, json_path)

    meta_dir = os.path.join(data_root, "mock_fan", "metadata")
    os.makedirs(meta_dir, exist_ok=True)
    save_provenance_metadata(meta, os.path.join(meta_dir, f"{base_name}.json"))

    return output_path, meta
