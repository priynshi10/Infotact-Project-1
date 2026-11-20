"""
AetherHound Signal Visualization & Plotting Utility with Full Data Provenance
Generates publication-quality Matplotlib figures with cryptographic metadata,
verifiable raw sample bindings, and explicit Live Hardware vs Synthetic labelling.
"""

from datetime import datetime, timezone
import os
import shutil
import time
from typing import Any, Dict, Optional, Tuple

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless / server environments
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf

from aetherhound.core.evidence_metadata import (
    SOURCE_TYPE_LIVE_HARDWARE,
    SOURCE_TYPE_SYNTHETIC_SIMULATION,
    compute_array_sha256,
    compute_file_sha256,
    generate_capture_id,
    get_display_source_label,
    normalize_source_type,
)
from aetherhound.dsp.provenance import (
    EvidenceProvenance,
    SourceModeType,
    save_provenance_metadata,
)


def _draw_provenance_header(
    fig,
    source_label: str,
    sensor_id: str,
    capture_id: str,
    timestamp_iso: str,
    raw_sha256: str,
    extra_info: str = "",
):
    """Draw a standardized, immutable provenance header on top of the Matplotlib figure."""
    is_hw = source_label == "LIVE HARDWARE"
    is_sim = source_label == "SYNTHETIC SIMULATION"
    bg_color = "#004d40" if is_hw else ("#263238" if is_sim else "#1a237e")
    border_color = "#00e676" if is_hw else ("#78909c" if is_sim else "#536dfe")
    tag_color = "#69f0ae" if is_hw else ("#b0bec5" if is_sim else "#8c9eff")

    header_text = (
        f"SOURCE: [{source_label}] | ID: {capture_id} | SENSOR: {sensor_id}\n"
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
        fontsize=7.5,
        fontfamily="monospace",
        fontweight="bold",
        color=tag_color,
        bbox=dict(
            boxstyle="square,pad=0.35",
            facecolor=bg_color,
            edgecolor=border_color,
            linewidth=1.2,
        ),
    )


def _mirror_to_public(output_path: str) -> None:
    """Mirror generated plot to public/ directory for Vite static previewing."""
    try:
        public_plot = os.path.join("public", output_path) if not output_path.startswith("public") else output_path
        os.makedirs(os.path.dirname(os.path.abspath(public_plot)), exist_ok=True)
        shutil.copy2(output_path, public_plot)
    except Exception:
        pass


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
    rf_gain: Any = "auto",
    fft_size: int = 2048,
    acquisition_mode: Optional[str] = None,
    capture_id: Optional[str] = None,
    timestamp_epoch: Optional[float] = None,
    title: str = "AetherHound Calibrated RF Spectrum",
    highlight_peak_hz: Optional[float] = None,
    peak_power_db: Optional[float] = None,
) -> Tuple[str, EvidenceProvenance]:
    """
    Save calibrated RF spectrum figure accompanied by raw IQ dump and Day 1 provenance JSON.
    """
    t_epoch = timestamp_epoch or time.time()
    t_iso = datetime.fromtimestamp(t_epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    norm_source_type = normalize_source_type(source_mode) or SOURCE_TYPE_SYNTHETIC_SIMULATION
    source_label = get_display_source_label(norm_source_type)
    cap_id = capture_id or generate_capture_id("RF")

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
        np.save(raw_path, spectrum_db)
        raw_hash = compute_array_sha256(spectrum_db)
        sample_count = len(spectrum_db)

    duration_sec = sample_count / sample_rate_hz if sample_rate_hz > 0 else 0.0
    acq_mode = acquisition_mode or (
        "RTL-SDR Hardware IQ Stream" if norm_source_type == SOURCE_TYPE_LIVE_HARDWARE
        else "Synthetic Complex IQ Simulation"
    )

    # 2. Render Matplotlib Figure
    fig, ax = plt.subplots(figsize=(10, 5.8), dpi=120)
    plt.subplots_adjust(top=0.84, bottom=0.12, left=0.10, right=0.95)

    freqs_mhz = frequencies_hz / 1e6
    line_color = "#00bcd4" if source_label == "LIVE HARDWARE" else "#00acc1"
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
        label_txt = f"Detector Anomaly: {highlight_peak_hz / 1e6:.3f} MHz"
        if dev > 0:
            label_txt += f" (+{dev:.1f} dB)"
        ax.axvline(highlight_peak_hz / 1e6, color="#f44336", linestyle=":", linewidth=1.5, label=label_txt)

    ax.set_title(title, fontsize=11, fontweight="bold", pad=10)
    ax.set_xlabel("RF Frequency (MHz)", fontsize=10)
    ax.set_ylabel("Power Spectral Density (dBFS)", fontsize=10)
    ax.set_ylim(-130, 0)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right", fontsize=8)

    _draw_provenance_header(
        fig,
        source_label=source_label,
        sensor_id=sensor_id,
        capture_id=cap_id,
        timestamp_iso=t_iso,
        raw_sha256=raw_hash,
        extra_info=f"Fc: {center_freq_hz / 1e6:.3f} MHz | Fs: {sample_rate_hz / 1e6:.3f} Msps | Gain: {rf_gain} | FFT: {fft_size} | N: {sample_count}",
    )

    fig.savefig(output_path)
    plt.close(fig)
    _mirror_to_public(output_path)

    # 3. Create Provenance Record
    meta = EvidenceProvenance(
        capture_id=cap_id,
        modality="RF",
        plot_path=output_path,
        source_mode=source_label,
        source_type=norm_source_type,
        data_source=source_label,
        sensor_id=sensor_id,
        acquisition_mode=acq_mode,
        capture_timestamp_iso=t_iso,
        capture_timestamp_epoch=t_epoch,
        sample_rate_hz=float(sample_rate_hz),
        center_freq_hz=float(center_freq_hz),
        rf_gain=rf_gain,
        fft_size=int(fft_size),
        recording_duration_sec=duration_sec,
        sample_count=int(sample_count),
        raw_data_path=raw_path,
        raw_data_sha256=raw_hash,
        device_verified=(norm_source_type == SOURCE_TYPE_LIVE_HARDWARE),
        detection_event_type="RF_SPECTRAL_ANOMALY" if highlight_peak_hz else None,
        metrics={
            "noise_floor_db": round(float(noise_floor_db), 2),
            "peak_freq_hz": round(float(highlight_peak_hz), 1) if highlight_peak_hz else 0.0,
            "peak_power_db": round(float(peak_power_db), 2) if peak_power_db else 0.0,
        },
        notes=f"Generated via AetherHound DSP FFT engine ({acq_mode}). Source tagged as {source_label}.",
    )

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
    channels: int = 1,
    audio_format: str = "float32",
    acquisition_mode: Optional[str] = None,
    capture_id: Optional[str] = None,
    timestamp_epoch: Optional[float] = None,
    title: str = "AetherHound Acoustic Waveform & Pulse Envelope",
    target_morse: Optional[str] = "SOS",
    match_score: Optional[float] = None,
) -> Tuple[str, EvidenceProvenance]:
    """
    Save acoustic waveform and envelope plot from acquired audio stream buffer.
    Guarantees separate raw WAV binding and Day 1 provenance metadata.
    """
    t_epoch = timestamp_epoch or time.time()
    t_iso = datetime.fromtimestamp(t_epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    norm_source_type = normalize_source_type(source_mode) or SOURCE_TYPE_SYNTHETIC_SIMULATION
    source_label = get_display_source_label(norm_source_type)
    cap_id = capture_id or generate_capture_id("MIC")

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
    acq_mode = acquisition_mode or (
        "PyAudio Non-Blocking Microphone Stream" if norm_source_type == SOURCE_TYPE_LIVE_HARDWARE
        else "Virtual Receiver Stream (Synthetic Signal Input)"
    )

    # 2. Render Matplotlib Figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6.8), sharex=True, dpi=120)
    plt.subplots_adjust(top=0.83, bottom=0.10, left=0.10, right=0.95, hspace=0.28)

    wave_color = "#4caf50" if source_label == "LIVE HARDWARE" else "#66bb6a"
    ax1.plot(times_sec, audio, color=wave_color, linewidth=0.8, alpha=0.85)
    ax1.set_title(title, fontsize=10, fontweight="bold")
    ax1.set_ylabel("Amplitude", fontsize=9)
    ax1.grid(True, linestyle=":", alpha=0.6)

    ax2.plot(times_sec, envelope, color="#e91e63", linewidth=1.4, label="Streaming Causal Envelope")
    env_title = "Extracted Pulse Amplitude Envelope"
    if match_score is not None:
        env_title += f" [Recognized {target_morse} | Score: {match_score * 100:.1f}%]"
    ax2.set_title(env_title, fontsize=10, fontweight="bold")
    ax2.set_xlabel("Time (seconds)", fontsize=9)
    ax2.set_ylabel("Envelope Power", fontsize=9)
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend(loc="upper right", fontsize=8)

    _draw_provenance_header(
        fig,
        source_label=source_label,
        sensor_id=sensor_id,
        capture_id=cap_id,
        timestamp_iso=t_iso,
        raw_sha256=raw_hash,
        extra_info=f"Fs: {sample_rate_hz} Hz | Ch: {channels} ({audio_format}) | Dur: {duration_sec:.2f}s | Frames: {sample_count}",
    )

    fig.savefig(output_path)
    plt.close(fig)
    _mirror_to_public(output_path)

    # 3. Create Provenance Record
    meta = EvidenceProvenance(
        capture_id=cap_id,
        modality="ACOUSTIC",
        plot_path=output_path,
        source_mode=source_label,
        source_type=norm_source_type,
        data_source=source_label,
        sensor_id=sensor_id,
        acquisition_mode=acq_mode,
        capture_timestamp_iso=t_iso,
        capture_timestamp_epoch=t_epoch,
        sample_rate_hz=float(sample_rate_hz),
        center_freq_hz=None,
        channels=int(channels),
        audio_format=str(audio_format),
        recording_duration_sec=duration_sec,
        sample_count=int(sample_count),
        raw_data_path=raw_wav_path,
        raw_data_sha256=raw_hash,
        device_verified=(norm_source_type == SOURCE_TYPE_LIVE_HARDWARE),
        detection_event_type="ACOUSTIC_MORSE_PATTERN" if match_score is not None else None,
        metrics={
            "duration_sec": round(duration_sec, 2),
            "match_score": round(match_score, 3) if match_score is not None else None,
            "target_pattern": target_morse or "",
        },
        notes=f"Captured from receiver stream ({acq_mode}). Source tagged as {source_label}.",
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
    sensor_id: str = "FAN-SIM-01 (SOFTWARE MODEL)",
    capture_id: Optional[str] = None,
    timestamp_epoch: Optional[float] = None,
    title: str = "AetherHound Benign Fan RPM Morse Trajectory [SIMULATED]",
    message: str = "SOS",
    simulation_parameters: Optional[Dict[str, Any]] = None,
) -> Tuple[str, EvidenceProvenance]:
    """
    Save fan RPM trajectory plot. Explicitly labels software simulation vs tachometer measurements.
    """
    t_epoch = timestamp_epoch or time.time()
    t_iso = datetime.fromtimestamp(t_epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    norm_source_type = normalize_source_type(source_mode) or SOURCE_TYPE_SYNTHETIC_SIMULATION
    source_label = get_display_source_label(norm_source_type)
    cap_id = capture_id or generate_capture_id("FANSIM")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    base_name = os.path.splitext(os.path.basename(output_path))[0]
    data_root = os.path.abspath(os.path.join(os.path.dirname(output_path), "..", ".."))

    sim_params = simulation_parameters or {
        "message": message,
        "base_rpm": 1200.0,
        "low_rpm": 900.0,
        "high_rpm": 1800.0,
        "dot_duration_sec": 0.20,
        "dash_duration_sec": 0.60,
        "time_step_sec": round(float(times_sec[1] - times_sec[0]), 4) if len(times_sec) > 1 else 0.02,
    }

    # Save CSV timeline
    csv_dir = os.path.join(data_root, "mock_fan", "rpm")
    os.makedirs(csv_dir, exist_ok=True)
    csv_path = os.path.join(csv_dir, f"{base_name}_timeline.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("time_sec,simulated_rpm,is_pulse\n")
        for t, r, p in zip(times_sec, rpms, pulse_states):
            f.write(f"{t:.4f},{r:.2f},{int(p)}\n")

    raw_hash = compute_file_sha256(csv_path)

    # Render figure
    fig, ax1 = plt.subplots(figsize=(10, 5.8), dpi=120)
    plt.subplots_adjust(top=0.83, bottom=0.14, left=0.10, right=0.90)

    color = "#2196f3"
    ax1.set_xlabel("Time (seconds)", fontsize=10)
    ax1.set_ylabel("Simulated Fan Speed (RPM)", color=color, fontsize=10)
    ax1.plot(times_sec, rpms, color=color, linewidth=2.0, label="Simulated Fan Trajectory (RPM)")
    ax1.tick_params(axis="y", labelcolor=color)

    ax2 = ax1.twinx()
    color2 = "#e91e63"
    ax2.set_ylabel("Morse Modulation State", color=color2, fontsize=10)
    ax2.fill_between(times_sec, 0, pulse_states.astype(int), color=color2, alpha=0.20, label="Simulated Pulse (Dot/Dash)")
    ax2.set_ylim(-0.1, 1.5)
    ax2.set_yticks([0, 1])
    ax2.set_yticklabels(["Idle (Gap)", "Active (Pulse)"])
    ax2.tick_params(axis="y", labelcolor=color2)

    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.set_title(title, fontsize=11, fontweight="bold", pad=10)

    fig.text(
        0.5,
        0.02,
        "SIMULATED RPM ONLY – BENIGN SOFTWARE MODEL – NO PHYSICAL MOTHERBOARD CONTROL OR TACHOMETER ATTACHED",
        ha="center",
        va="bottom",
        fontsize=7,
        fontfamily="monospace",
        fontweight="bold",
        color="#ffa726",
    )

    _draw_provenance_header(
        fig,
        source_label=source_label,
        sensor_id=sensor_id,
        capture_id=cap_id,
        timestamp_iso=t_iso,
        raw_sha256=raw_hash,
        extra_info=f"Target: {message} | RPM: SIMULATED ({sim_params.get('low_rpm', 900):.0f}-{sim_params.get('high_rpm', 1800):.0f})",
    )

    fig.savefig(output_path)
    plt.close(fig)
    _mirror_to_public(output_path)

    sample_rate_hz = round(1.0 / (times_sec[1] - times_sec[0]), 2) if len(times_sec) > 1 else 50.0
    meta = EvidenceProvenance(
        capture_id=cap_id,
        modality="FAN_SIMULATION",
        plot_path=output_path,
        source_mode=source_label,
        source_type=norm_source_type,
        data_source=source_label,
        sensor_id=sensor_id,
        acquisition_mode="Software Aerodynamic Simulation (No Tachometer)",
        capture_timestamp_iso=t_iso,
        capture_timestamp_epoch=t_epoch,
        sample_rate_hz=sample_rate_hz,
        center_freq_hz=None,
        recording_duration_sec=float(times_sec[-1]),
        sample_count=len(times_sec),
        raw_data_path=csv_path,
        raw_data_sha256=raw_hash,
        device_verified=False,
        simulation_parameters=sim_params,
        detection_event_type="FAN_RPM_SIMULATION",
        metrics={
            "base_rpm": float(sim_params.get("base_rpm", 1200.0)),
            "low_rpm": float(sim_params.get("low_rpm", 900.0)),
            "high_rpm": float(sim_params.get("high_rpm", 1800.0)),
            "message": message,
        },
        notes="Software simulation of aerodynamic fan speed profile for laboratory detection calibration. RPM values are SIMULATED.",
    )

    json_path = os.path.splitext(output_path)[0] + ".json"
    save_provenance_metadata(meta, json_path)

    meta_dir = os.path.join(data_root, "mock_fan", "metadata")
    os.makedirs(meta_dir, exist_ok=True)
    save_provenance_metadata(meta, os.path.join(meta_dir, f"{base_name}.json"))

    return output_path, meta
