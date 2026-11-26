"""
AetherHound Real-Time Terminal Monitoring Interface
Full-screen live telemetry display built with Rich.
Presents dual-channel RF & Acoustic SIGINT surveillance, anomaly indicators,
and keyboard controls.
"""

import os
import argparse
import select
import sys
import time
try:
    import termios
    import tty
except ImportError:
    termios = None
    tty = None
from typing import Literal, Optional
import numpy as np
import soundfile as sf

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from aetherhound.core.realtime_engine import EngineTelemetry, RealtimeEngine
from aetherhound.hardware.config import HardwareConfig
from aetherhound.hardware.rf_capture import IQSampleWindow
from aetherhound.hardware.acoustic_capture import AudioChunk


class LiveMonitorInterface:
    """
    Continuous Rich terminal dashboard for AetherHound.
    Renders live sensor health, FFT spectrum telemetry, acoustic features,
    and alert event tables.
    """

    def __init__(
        self,
        engine: RealtimeEngine,
        refresh_rate_hz: float = 4.0,
        operating_mode: Literal["DEMO", "FILE", "HARDWARE"] = "DEMO",
        signal_type: Literal["ACOUSTIC", "RF"] = "RF",
        input_path: Optional[str] = None,
        detector_type: str = "numpy_baseline",
        model_dir: str = "data/models/anomaly",
    ):
        self.engine = engine
        self.refresh_rate_hz = refresh_rate_hz
        self.console = Console()
        self._is_running = False
        self.operating_mode = operating_mode
        self.signal_type = signal_type
        self.input_path = input_path
        self.detector_type = detector_type
        self.model_dir = model_dir
        self.detector = None
        self._load_detector()

    def _load_detector(self) -> None:
        try:
            if self.detector_type == "pytorch_autoencoder":
                from aetherhound.detection.anomaly_detector import PyTorchAutoencoderDetector
                self.detector = PyTorchAutoencoderDetector.load(self.model_dir)
            else:
                from aetherhound.detection.anomaly_detector import NumPyAnomalyDetector
                self.detector = NumPyAnomalyDetector.load(self.model_dir)
        except (FileNotFoundError, RuntimeError, ValueError):
            self.detector = None

    def build_layout(self, tel: EngineTelemetry) -> Layout:
        """Construct the Rich terminal layout tree."""
        layout = Layout()
        tel.baseline_model_status = (
            f"{self.detector_type}: TRAINED"
            if self.detector is not None
            else f"{self.detector_type}: NOT TRAINED"
        )

        # Main vertical split: Header, Body, Events, Footer
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=2),
            Layout(name="spectrum", size=7),
            Layout(name="waterfall", size=10),
            Layout(name="events", size=8),
            Layout(name="footer", size=3),
        )

        # Body horizontal split: RF Panel, Acoustic Panel, Detection Panel
        layout["body"].split_row(
            Layout(name="rf_monitor", ratio=1),
            Layout(name="acoustic_monitor", ratio=1),
            Layout(name="detection_status", ratio=1),
        )

        # 1. Header
        paused_tag = " [bold red][PAUSED][/bold red]" if tel.is_paused else ""
        header_text = Text.from_markup(
            f"[bold cyan]AETHERHOUND[/bold cyan] – [bold white]LIVE DSP WATERFALL[/bold white]{paused_tag} "
            f"[dim]| Mode: {self.operating_mode} | Signal: {self.signal_type} | "
            f"Uptime: {tel.uptime_sec:.1f}s | {time.strftime('%Y-%m-%d %H:%M:%S')}[/dim]"
        )
        layout["header"].update(Panel(header_text, style="blue"))

        # 2. RF Monitoring Panel
        rf_color = "green" if tel.rf_status == "NORMAL" else "bold red"
        rf_table = Table(box=None, show_header=False, expand=True)
        rf_conn_str = "[bold green]CONNECTED[/bold green]" if tel.rf_connected else "[bold yellow]DISCONNECTED (Synthetic)[/bold yellow]"
        rf_table.add_row("Status:", rf_conn_str)
        rf_table.add_row("Center Frequency:", f"{tel.rf_center_freq_hz / 1e6:.3f} MHz")
        rf_table.add_row("Sample Rate:", f"{tel.rf_sample_rate_hz / 1e6:.3f} Msps")
        rf_table.add_row("Noise Floor:", f"{tel.rf_noise_floor_db:.1f} dBFS")
        rf_table.add_row("Peak Power:", f"{tel.rf_peak_power_db:.1f} dBFS")
        rf_table.add_row("Peak Frequency:", f"{tel.rf_peak_freq_hz / 1e6:.3f} MHz")
        rf_table.add_row("DSP Latency:", f"{tel.rf_processing_latency_ms:.1f} ms")
        rf_table.add_row("Queue / Dropped:", f"{tel.rf_queue_fill} / {tel.rf_dropped_windows}")

        layout["rf_monitor"].update(
            Panel(rf_table, title="[bold cyan]RF MONITORING (SDR-01)[/bold cyan]", border_style="cyan")
        )

        # 3. Acoustic Monitoring Panel
        mic_table = Table(box=None, show_header=False, expand=True)
        mic_conn_str = "[bold green]CONNECTED[/bold green]" if tel.mic_connected else "[bold yellow]DISCONNECTED (Synthetic)[/bold yellow]"
        mic_table.add_row("Status:", mic_conn_str)
        mic_table.add_row("Sample Rate:", f"{tel.acoustic_sample_rate_hz} Hz")
        mic_table.add_row("RMS Energy:", f"{tel.acoustic_rms_energy:.5f}")
        mic_table.add_row("Dominant Freq:", f"{tel.acoustic_dominant_freq_hz:.1f} Hz")
        mic_table.add_row("DSP Latency:", f"{tel.acoustic_processing_latency_ms:.1f} ms")
        mic_table.add_row("Queue / Dropped:", f"{tel.acoustic_queue_fill} / {tel.acoustic_dropped_chunks}")
        mic_table.add_row("Chunks Processed:", str(tel.acoustic_chunks_processed))

        layout["acoustic_monitor"].update(
            Panel(mic_table, title="[bold green]ACOUSTIC MONITORING (MIC-01)[/bold green]", border_style="green")
        )

        # 4. Detection Status Panel
        det_table = Table(box=None, show_header=False, expand=True)
        rf_alert_str = f"[{rf_color}]{tel.rf_status}[/{rf_color}]"
        ac_alert_str = "[bold red]SUSPICIOUS[/bold red]" if tel.acoustic_status == "SUSPICIOUS" else "[green]NORMAL[/green]"
        morse_alert_str = "[bold red blink]PATTERN DETECTED (SOS)![/bold red blink]" if tel.morse_status == "PATTERN DETECTED" else "[dim]NO PATTERN[/dim]"

        det_table.add_row("[bold]RF CHANNEL:[/bold]", rf_alert_str)
        det_table.add_row("[bold]ACOUSTIC BURST:[/bold]", ac_alert_str)
        det_table.add_row("[bold]MORSE SEQUENCE:[/bold]", morse_alert_str)
        det_table.add_row("[bold]ML BASELINE:[/bold]", tel.baseline_model_status)
        if tel.anomaly_score is not None and tel.anomaly_threshold is not None:
            det_table.add_row("[bold]ML SCORE:[/bold]", f"{tel.anomaly_score:.6f} / {tel.anomaly_threshold:.6f}")
            det_table.add_row("[bold]ML STATUS:[/bold]", tel.anomaly_status)
        det_table.add_row("", "")
        det_table.add_row("[dim]Target Signature:[/dim]", "[dim]SOS (... --- ...)[/dim]")
        det_table.add_row("[dim]Threat Vector:[/dim]", "[dim]CPU Fan PWM Covert Exfil[/dim]")

        layout["detection_status"].update(
            Panel(det_table, title="[bold magenta]DETECTION STATUS[/bold magenta]", border_style="magenta")
        )

        spectrum_panel = self._build_spectrum_panel(tel)
        layout["spectrum"].update(spectrum_panel)
        layout["waterfall"].update(self._build_waterfall_panel())

        # 5. Events Table
        event_table = Table(box=None, expand=True)
        event_table.add_column("Timestamp", style="cyan", width=12)
        event_table.add_column("Sensor", style="yellow", width=10)
        event_table.add_column("Event", style="bold white", width=34)
        event_table.add_column("Evidence & Telemetry", style="dim")

        if tel.recent_events:
            for ev in list(tel.recent_events)[-4:]:
                event_table.add_row(
                    ev.get("timestamp", "-"),
                    ev.get("sensor", "-"),
                    ev.get("event", "-"),
                    ev.get("evidence", "-"),
                )
        else:
            event_table.add_row(
                time.strftime("%H:%M:%S"),
                "SYSTEM",
                "Acquisition Active",
                "Baseline ambient signals within statistical threshold bounds",
            )

        layout["events"].update(
            Panel(event_table, title="[bold]RECENT COVERT CHANNEL EVENTS[/bold]", border_style="white")
        )

        # 6. Controls Footer
        footer_text = Text.from_markup(
            "[bold white]CONTROLS:[/bold white] "
            "[bold cyan]S[/bold cyan] = Start  |  "
            "[bold yellow]P[/bold yellow] = Pause  |  "
            "[bold green]R[/bold green] = Resume  |  "
            "[bold red]X[/bold red] = Stop  |  "
            "[bold cyan]A[/bold cyan] = Acoustic  |  "
            "[bold yellow]F[/bold yellow] = RF  |  "
            "[bold magenta]Q[/bold magenta] = Quit"
        )
        layout["footer"].update(Panel(footer_text, style="dim"))

        return layout

    def _build_spectrum_panel(self, tel: EngineTelemetry) -> Panel:
        if self.signal_type == "RF":
            processed = self.engine.rf_processor.latest_processed
            if processed is not None:
                freqs = processed.frequencies_hz
                spectrum = processed.spectrum_db
            else:
                freqs = np.array([0.0])
                spectrum = np.array([-120.0])
            status = tel.rf_status
            peak_freq = tel.rf_peak_freq_hz
            peak_power = tel.rf_peak_power_db
            filter_text = (
                f"FIR LOW-PASS {self.engine.config.rf.rf_filter_cutoff_hz / 1e3:.1f} kHz "
                f"| taps {self.engine.config.rf.rf_filter_taps}"
            )
        else:
            processed = self.engine.acoustic_processor.latest_processed
            if processed is not None:
                filtered = processed.filtered_samples
                freqs = np.fft.rfftfreq(len(filtered), d=1.0 / max(1, processed.sample_rate_hz))
                spectrum_db = 20.0 * np.log10(
                    np.maximum(np.abs(np.fft.rfft(filtered * np.hanning(len(filtered)))), 1e-12)
                )
                spectrum = spectrum_db
                peak_idx = int(np.argmax(spectrum)) if len(spectrum) else 0
                peak_freq = float(freqs[peak_idx]) if len(freqs) else 0.0
                peak_power = float(spectrum[peak_idx]) if len(spectrum) else -120.0
            else:
                freqs = np.array([0.0])
                spectrum = np.array([-120.0])
                peak_freq = 0.0
                peak_power = -120.0
            status = tel.acoustic_status
            filter_text = "FIR LOW-PASS 8.0 kHz + 50 Hz-8 kHz bandpass"

        width = max(20, min(100, self.console.size.width - 8))
        bins = np.linspace(0, len(spectrum) - 1, width).astype(int) if len(spectrum) else np.array([0])
        sampled = spectrum[bins] if len(spectrum) else np.array([-120.0])
        low = max(-120.0, float(np.min(sampled)))
        high = max(low + 1.0, float(np.max(sampled)))
        chars = " .:-=+*#%@"
        line = "".join(
            chars[int(np.clip((value - low) / (high - low) * (len(chars) - 1), 0, len(chars) - 1))]
            for value in sampled
        )
        table = Table(box=None, show_header=False, expand=True)
        table.add_row("Spectrum:", line)
        table.add_row(
            "Peak:",
            f"{peak_freq / 1e3 if self.signal_type == 'RF' else peak_freq:.1f}"
            f"{' kHz offset' if self.signal_type == 'RF' else ' Hz'} "
            f"{peak_power:.1f} dB",
        )
        table.add_row("Status:", f"{status} | Latency: "
            f"{tel.rf_processing_latency_ms if self.signal_type == 'RF' else tel.acoustic_processing_latency_ms:.2f} ms")
        table.add_row("Filter:", filter_text)
        table.add_row(
            "Processing:",
            f"{'PYTHON NumPy/SciPy fallback' if self.operating_mode == 'DEMO' or self.operating_mode == 'FILE' else 'RF/acoustic engine'} "
            f"| frames: {tel.rf_windows_processed if self.signal_type == 'RF' else tel.acoustic_chunks_processed}",
        )
        return Panel(table, title="[bold yellow]CURRENT FREQUENCY SPECTRUM[/bold yellow]", border_style="yellow")

    def _build_waterfall_panel(self) -> Panel:
        processor = (
            self.engine.rf_processor
            if self.signal_type == "RF"
            else self.engine.acoustic_processor
        )
        waterfall = processor.waterfall if self.signal_type == "RF" else processor.spectrogram
        matrix, _, _ = waterfall.get_waterfall_matrix()
        if len(matrix) == 1 and not np.any(matrix):
            matrix = np.full((1, max(8, waterfall.num_bins)), -120.0)

        height = max(4, min(8, self.console.size.height // 8))
        width = max(20, min(100, self.console.size.width - 8))
        row_indices = np.linspace(0, matrix.shape[0] - 1, height).astype(int)
        bin_indices = np.linspace(0, matrix.shape[1] - 1, width).astype(int)
        data = matrix[np.ix_(row_indices, bin_indices)]
        finite = data[np.isfinite(data)]
        low = float(np.percentile(finite, 5)) if finite.size else -120.0
        high = float(np.percentile(finite, 95)) if finite.size else -40.0
        if high <= low:
            high = low + 1.0
        chars = " .:-=+*#%@"
        lines = []
        for row in data:
            lines.append("".join(
                chars[int(np.clip((float(v) - low) / (high - low) * (len(chars) - 1), 0, len(chars) - 1))]
                for v in row
            ))
        return Panel(
            Text("\n".join(reversed(lines)), style="cyan"),
            title="[bold cyan]ROLLING SPECTROGRAM WATERFALL (NEWEST ABOVE)[/bold cyan]",
            border_style="cyan",
        )

    def _load_file_frames(self, input_path: str):
        if input_path.lower().endswith(".wav"):
            data, sample_rate = sf.read(input_path, dtype="float32", always_2d=False)
            if data.ndim == 2:
                data = np.mean(data, axis=1)
            chunk_size = self.engine.config.acoustic.chunk_size
            frames = []
            for index, offset in enumerate(range(0, len(data), chunk_size), start=1):
                chunk = data[offset:offset + chunk_size]
                if len(chunk) < 2:
                    continue
                frames.append(AudioChunk(
                    samples=chunk.astype(np.float32),
                    timestamp=time.time(),
                    sample_rate_hz=int(sample_rate),
                    channels=1,
                    is_synthetic=False,
                    chunk_id=index,
                    source_type="RECORDED_HARDWARE",
                ))
            self.signal_type = "ACOUSTIC"
            return frames

        data = np.load(input_path, allow_pickle=False)
        if data.ndim != 1:
            raise ValueError("Evidence .npy files must contain a one-dimensional sample array")
        chunk_size = min(self.engine.config.rf.samples_per_window, len(data))
        if chunk_size < 2:
            raise ValueError("Evidence file contains too few samples")
        frames = []
        for index, offset in enumerate(range(0, len(data), chunk_size), start=1):
            chunk = data[offset:offset + chunk_size]
            if len(chunk) < 2:
                continue
            frames.append(IQSampleWindow(
                samples=np.asarray(chunk),
                timestamp=time.time(),
                center_freq_hz=self.engine.config.rf.center_freq_hz,
                sample_rate_hz=self.engine.config.rf.sample_rate_hz,
                is_synthetic=False,
                window_id=index,
                source_type="RECORDED_HARDWARE",
            ))
        self.signal_type = "RF"
        return frames

    def run(self, max_seconds: Optional[float] = None) -> None:
        """Run the live terminal interface loop."""
        self._is_running = True
        file_frames = []
        if self.operating_mode == "FILE" and self.input_path:
            file_frames = self._load_file_frames(self.input_path)
        else:
            self.engine.start()
        file_index = 0

        is_tty = sys.stdin.isatty()
        old_settings = None
        if is_tty and termios is not None and tty is not None:
            try:
                old_settings = termios.tcgetattr(sys.stdin)
                tty.setcbreak(sys.stdin.fileno())
            except Exception:
                is_tty = False

        start_time = time.time()
        try:
            with Live(
                self.build_layout(self.engine.get_telemetry()),
                refresh_per_second=self.refresh_rate_hz,
                screen=True,
            ) as live:
                while self._is_running:
                    # Check timeout if specified
                    if max_seconds and (time.time() - start_time) >= max_seconds:
                        break

                    # Process non-blocking keyboard input
                    if is_tty and termios is not None and tty is not None and select.select([sys.stdin], [], [], 0.0)[0]:
                        try:
                            char = sys.stdin.read(1).upper()
                            if char == "Q" or char == "X":
                                self.engine.stop()
                                break
                            elif char == "P":
                                self.engine.pause()
                            elif char == "R":
                                self.engine.resume()
                            elif char == "S":
                                if not self.engine.is_running:
                                    self.engine.start()
                            elif char == "A":
                                self.signal_type = "ACOUSTIC"
                            elif char == "F":
                                self.signal_type = "RF"
                        except Exception:
                            pass

                    if self.operating_mode == "FILE" and file_frames:
                        if file_index < len(file_frames):
                            frame = file_frames[file_index]
                            if self.signal_type == "RF":
                                self.engine.process_external_rf_window(frame)
                            else:
                                self.engine.process_external_acoustic_chunk(frame)
                            file_index += 1
                        else:
                            file_index = 0

                    # Update terminal display
                    tel = self.engine.get_telemetry()
                    live.update(self.build_layout(tel))
                    time.sleep(1.0 / self.refresh_rate_hz)

        finally:
            if is_tty and old_settings:
                try:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                except Exception:
                    pass
            self.engine.stop()
            self._is_running = False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AetherHound live spectrum and waterfall monitor")
    parser.add_argument("--mode", choices=("demo", "file", "hardware"), default="demo")
    parser.add_argument("--signal", choices=("acoustic", "rf"), default="rf")
    parser.add_argument("--input", dest="input_path", help="WAV or NPY evidence file for file mode")
    parser.add_argument("--refresh", type=float, default=4.0)
    parser.add_argument("--seconds", type=float, default=None)
    parser.add_argument("--detector", choices=("numpy_baseline", "pytorch_autoencoder"), default="numpy_baseline")
    parser.add_argument("--model-dir", default="data/models/anomaly")
    args = parser.parse_args()

    cfg = HardwareConfig()
    if args.mode == "demo":
        engine = RealtimeEngine(
            config=cfg,
            synthetic_rf=True,
            synthetic_audio=True,
        )
        operating_mode = "DEMO"
    elif args.mode == "file":
        if not args.input_path:
            parser.error("--input is required when --mode file")
        engine = RealtimeEngine(config=cfg, synthetic_rf=False, synthetic_audio=False)
        operating_mode = "FILE"
    else:
        from aetherhound.hardware.device_check import run_diagnostics
        diag = run_diagnostics(cfg)
        engine = RealtimeEngine(
            config=cfg,
            synthetic_rf=not diag.sdr_device.connected,
            synthetic_audio=not diag.mic_device.connected,
        )
        operating_mode = "HARDWARE"

    monitor = LiveMonitorInterface(
        engine,
        refresh_rate_hz=args.refresh,
        operating_mode=operating_mode,
        signal_type=args.signal.upper(),
        input_path=args.input_path,
        detector_type=args.detector,
        model_dir=args.model_dir,
    )
    print("Launching AetherHound Live Terminal Monitor...")
    monitor.run(max_seconds=args.seconds)
