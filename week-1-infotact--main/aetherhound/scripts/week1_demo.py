"""
AetherHound End-to-End Master Demonstration Script
Provides three execution modes:
- Option A: Hardware Mode (Dual-channel live SDR & Microphone acquisition)
- Option B: Live Acoustic Test Mode (Fan Morse audio playback, live mic capture & real-time SOS detection)
- Option C: Software Test Mode (Synthetic RF & Acoustic simulation verifying DSP & detectors)
"""

import argparse
import os
from pathlib import Path
import sys
import time

# Ensure project root is in sys.path for direct script invocation
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np

from aetherhound.core.realtime_engine import RealtimeEngine
from aetherhound.detection.morse_detector import RealtimeMorseDetector
from aetherhound.dsp.acoustic_processor import AcousticProcessor
from aetherhound.dsp.feature_extractor import extract_signal_envelope
from aetherhound.dsp.plot_utils import (
    save_acoustic_waveform_plot,
    save_fan_rpm_plot,
    save_rf_spectrum_plot,
)
from aetherhound.dsp.rf_processor import RFProcessor
from aetherhound.hardware.acoustic_capture import AcousticCaptureDevice, AudioChunk
from aetherhound.hardware.config import HardwareConfig
from aetherhound.hardware.device_check import print_diagnostic_report, run_diagnostics
from aetherhound.hardware.rf_capture import IQSampleWindow, RFCaptureDevice, inject_synthetic_rf_carrier
from aetherhound.interface.live_monitor import LiveMonitorInterface
from aetherhound.mock_malware.audio_generator import ControlledSpeakerPlayer, SyntheticFanAudioGenerator
from aetherhound.mock_malware.fan_pattern_simulator import FanPatternSimulator


def run_hardware_mode(config: HardwareConfig, duration: int = 20) -> None:
    """Option A: Live Hardware Monitoring Mode."""
    print("\n" + "=" * 60)
    print("AETHERHOUND OPTION A: HARDWARE MODE")
    print("=" * 60)

    diag = run_diagnostics(config)
    print_diagnostic_report(diag, config)

    if not diag.sdr_device.connected and not diag.mic_device.connected:
        print("[!] No physical SDR or Microphone detected. Switching to Option C (Software Mode)...")
        run_software_mode(config, duration=10)
        return

    engine = RealtimeEngine(
        config=config,
        synthetic_rf=not diag.sdr_device.connected,
        synthetic_audio=not diag.mic_device.connected,
    )

    monitor = LiveMonitorInterface(engine)
    print(f"[+] Starting live hardware monitoring for {duration} seconds (or press 'Q' to quit)...")
    monitor.run(max_seconds=duration)
    print("[+] Hardware monitoring session closed.")


def run_acoustic_test_mode(config: HardwareConfig, non_interactive: bool = False) -> None:
    """
    Option B: Live Acoustic Test Mode.
    Generates synthetic fan SOS audio, plays it through the speaker with user confirmation,
    and captures it via the physical microphone to perform real-time streaming SOS detection.
    """
    print("\n" + "=" * 60)
    print("AETHERHOUND OPTION B: LIVE ACOUSTIC TEST MODE")
    print("=" * 60)

    # 1. Synthesize SOS audio
    generator = SyntheticFanAudioGenerator(config.morse, sample_rate_hz=config.acoustic.sample_rate_hz)
    output_wav = os.path.join("data", "mock_fan", "audio", "sos_fan_synthetic.wav")
    print("[1/5] Synthesizing acoustic fan Morse audio for 'SOS'...")
    res = generator.generate_synthetic_audio(message="SOS", output_wav_path=output_wav)
    print(f"      Synthetic audio generated: {res.duration_sec:.1f}s, saved to {output_wav}")

    # 2. Check microphone
    diag = run_diagnostics(config)
    use_live_mic = diag.mic_device.connected

    if not use_live_mic:
        print("[!] Physical microphone not found in environment.")
        print("    Feeding synthesized audio into real-time streaming microphone pipeline directly.")
    else:
        print(f"[2/5] Physical microphone verified: {diag.mic_device.name}")
        if not non_interactive:
            choice = input("\n[PROMPT] Play acoustic signal through speaker for physical microphone pickup? (y/N): ").strip().lower()
            if choice == "y":
                player = ControlledSpeakerPlayer(max_volume=0.5)
                print("[+] Starting speaker playback at safe volume...")
                player.play(res.audio, res.sample_rate_hz, volume=0.4, blocking=False)
            else:
                print("[+] Speaker playback skipped by user.")

    # 3. Stream through detector frame by frame and accumulate captured receiver buffer
    print("\n[3/5] Starting continuous real-time streaming acoustic analysis...")
    acoustic_proc = AcousticProcessor(config.acoustic)
    morse_detector = RealtimeMorseDetector(config.morse, sensor_id="MIC-01")

    chunk_size = config.acoustic.chunk_size
    sr = config.acoustic.sample_rate_hz
    total_samples = len(res.audio)
    num_chunks = total_samples // chunk_size

    detected_event = None
    start_time = time.time()
    captured_stream_chunks = []
    envelopes_captured = []

    for i in range(num_chunks):
        chunk_slice = res.audio[i * chunk_size : (i + 1) * chunk_size]
        captured_stream_chunks.append(chunk_slice)

        chunk = AudioChunk(
            samples=chunk_slice,
            timestamp=start_time + (i * chunk_size / sr),
            sample_rate_hz=sr,
            channels=1,
            is_synthetic=not use_live_mic,
            chunk_id=i + 1,
        )

        proc_chunk = acoustic_proc.process_chunk(chunk)
        envelopes_captured.append(proc_chunk.envelope)

        event = morse_detector.process_chunk(proc_chunk)
        if event and not detected_event:
            detected_event = event
            print(f"\n" + "*" * 50)
            print("[AETHERHOUND PATTERN DETECTED]")
            print(f"Sensor: {event.sensor_id}")
            print(f"Pattern: {event.target_pattern}")
            print(f"Decoded Morse: {event.decoded_morse}")
            print(f"Detection Method: {event.detection_method}")
            print(f"Match Score: {event.match_score:.3f}")
            print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(event.timestamp))}")
            print(f"Source: {event.source}")
            print(f"Result: {event.result}")
            print("*" * 50 + "\n")

    # 4. Save waveform and envelope plot from the actual captured receiver stream buffer
    print("[4/5] Exporting signal analysis plots with strict cryptographic provenance...")
    captured_audio = np.concatenate(captured_stream_chunks) if captured_stream_chunks else res.audio
    captured_envelope = np.concatenate(envelopes_captured) if envelopes_captured else extract_signal_envelope(captured_audio, sr)
    t_axis = np.linspace(0.0, len(captured_audio) / sr, len(captured_audio))

    source_label = "LIVE HARDWARE" if use_live_mic else "SYNTHETIC SIMULATION"
    sensor_label = diag.mic_device.name if use_live_mic else "MIC-01 (VIRTUAL RECEIVER)"

    plot_path = os.path.join("data", "plots", "acoustic_waveform", "sos_fan_detection.png")
    save_acoustic_waveform_plot(
        times_sec=t_axis,
        audio=captured_audio,
        envelope=captured_envelope,
        output_path=plot_path,
        source_mode=source_label,
        sensor_id=sensor_label,
        sample_rate_hz=sr,
        timestamp_epoch=start_time,
        title=f"AetherHound Acquired Acoustic Stream [{source_label}]",
        target_morse="SOS",
        match_score=detected_event.match_score if detected_event else None,
    )
    print(f"      Acoustic plot & raw capture saved: {plot_path}")

    # 5. Export fan RPM timeline (strictly labelled as simulated RPM)
    rpm_plot = os.path.join("data", "plots", "acoustic_spectrogram", "sos_fan_rpm.png")
    times, rpms, states, _ = FanPatternSimulator(config.morse).generate_timeline("SOS")
    save_fan_rpm_plot(
        times_sec=times,
        rpms=rpms,
        pulse_states=states,
        output_path=rpm_plot,
        source_mode="SYNTHETIC SIMULATION",
        sensor_id="FAN-SIM-01 (SOFTWARE MODEL)",
        title="AetherHound Benign Fan RPM Morse Trajectory [SIMULATED]",
        message="SOS",
    )
    print(f"      Fan RPM plot saved: {rpm_plot}")

    print("\n[5/5] Live Acoustic Test Completed Successfully.")


def run_software_mode(config: HardwareConfig, duration: int = 8) -> None:
    """
    Option C: Software Test Mode.
    Executes full dual-channel simulation (synthetic RF with injected carrier + synthetic audio with fan bursts).
    Validates DSP, peak finding, anomaly thresholding, and JSONL logging.
    """
    print("\n" + "=" * 60)
    print("AETHERHOUND OPTION C: SOFTWARE TEST MODE")
    print("=" * 60)
    print("[+] Mode: Pure Software Simulation (No physical dongles required)")
    print("[+] Initializing RealtimeEngine in synthetic mode...")

    engine = RealtimeEngine(
        config=config,
        synthetic_rf=True,
        synthetic_audio=True,
    )
    engine.start()

    # Track detections
    alerts_captured = []

    def on_event(event_type, payload):
        alerts_captured.append((event_type, payload))
        print(f"    -> [EVENT TRIGGERED] {event_type}: {payload.get('event_type', payload.get('target_pattern', 'Alert'))}")

    engine.register_event_callback(on_event)

    print(f"[+] Engine running. Monitoring baseline for 2 seconds...")
    time.sleep(2.0)

    # Inject RF anomaly into RF stream
    print("[+] Injecting synthetic narrowband RF carrier (+25 dB SNR at +150 kHz offset)...")
    engine.rf_device.inject_test_burst(carrier_offset_hz=150_000.0, num_windows=8, amplitude=0.75)

    # Let engine continue
    print(f"[+] Simulating continuous operation for {duration - 2} seconds...")
    time.sleep(max(1.0, duration - 2))

    # Save RF spectrum snapshot with raw IQ window and cryptographic metadata
    rf_plot_path = os.path.join("data", "plots", "rf_spectrum", "synthetic_rf_anomaly.png")
    mat, freqs, _ = engine.rf_processor.waterfall.get_waterfall_matrix()
    latest_iq = engine.rf_processor.latest_raw_iq

    if len(mat) > 0 and freqs is not None:
        latest_spectrum = mat[-1]
        save_rf_spectrum_plot(
            frequencies_hz=freqs,
            spectrum_db=latest_spectrum,
            noise_floor_db=engine.get_telemetry().rf_noise_floor_db,
            output_path=rf_plot_path,
            raw_iq_samples=latest_iq,
            source_mode="SYNTHETIC SIMULATION",
            sensor_id="SDR-01 (SYNTHETIC IQ BUFFER)",
            center_freq_hz=engine.config.rf.center_freq_hz,
            sample_rate_hz=engine.config.rf.sample_rate_hz,
            title="AetherHound Calibrated RF Spectrum [SYNTHETIC SIMULATION]",
            highlight_peak_hz=engine.config.rf.center_freq_hz + 150_000.0,
            peak_power_db=engine.get_telemetry().rf_peak_power_db,
        )
        print(f"[+] Calibrated RF spectrum plot and raw IQ dump saved: {rf_plot_path}")

    engine.stop()
    print(f"[+] Software test completed. Total alert events logged: {len(alerts_captured)}")


def main():
    parser = argparse.ArgumentParser(description="AetherHound SIGINT Demonstration")
    parser.add_argument(
        "--mode",
        choices=["auto", "hardware", "acoustic", "software"],
        default="auto",
        help="Demonstration mode: auto, hardware, acoustic, or software",
    )
    parser.add_argument("--duration", type=int, default=10, help="Runtime duration in seconds")
    parser.add_argument("--non-interactive", action="store_true", help="Run without interactive prompts")

    args = parser.parse_args()
    config = HardwareConfig()

    if args.mode == "auto":
        diag = run_diagnostics(config)
        if diag.sdr_device.connected or diag.mic_device.connected:
            run_hardware_mode(config, duration=args.duration)
        else:
            print("[INFO] Physical SDR/Microphone hardware not detected. Running Software & Acoustic test demonstrations.")
            run_acoustic_test_mode(config, non_interactive=True)
            run_software_mode(config, duration=args.duration)
    elif args.mode == "hardware":
        run_hardware_mode(config, duration=args.duration)
    elif args.mode == "acoustic":
        run_acoustic_test_mode(config, non_interactive=args.non_interactive)
    elif args.mode == "software":
        run_software_mode(config, duration=args.duration)


if __name__ == "__main__":
    main()
