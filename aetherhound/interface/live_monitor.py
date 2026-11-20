"""
AetherHound Real-Time Terminal Monitoring Interface
Full-screen live telemetry display built with Rich.
Presents dual-channel RF & Acoustic SIGINT surveillance, anomaly indicators,
and keyboard controls.
"""

import os
import select
import sys
import termios
import time
import tty
from typing import Optional

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from aetherhound.core.realtime_engine import EngineTelemetry, RealtimeEngine
from aetherhound.hardware.config import HardwareConfig


class LiveMonitorInterface:
    """
    Continuous Rich terminal dashboard for AetherHound.
    Renders live sensor health, FFT spectrum telemetry, acoustic features,
    and alert event tables.
    """

    def __init__(self, engine: RealtimeEngine, refresh_rate_hz: float = 4.0):
        self.engine = engine
        self.refresh_rate_hz = refresh_rate_hz
        self.console = Console()
        self._is_running = False

    def build_layout(self, tel: EngineTelemetry) -> Layout:
        """Construct the Rich terminal layout tree."""
        layout = Layout()

        # Main vertical split: Header, Body, Events, Footer
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=2),
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
            f"[bold cyan]AETHERHOUND[/bold cyan] – [bold white]AIR-GAPPED RF & ACOUSTIC COVERT CHANNEL MONITOR[/bold white]{paused_tag} "
            f"[dim]| Uptime: {tel.uptime_sec:.1f}s | Mode: {'Hardware' if tel.rf_connected and tel.mic_connected else 'Laboratory Synthetic'}[/dim]"
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
        det_table.add_row("", "")
        det_table.add_row("[dim]Target Signature:[/dim]", "[dim]SOS (... --- ...)[/dim]")
        det_table.add_row("[dim]Threat Vector:[/dim]", "[dim]CPU Fan PWM Covert Exfil[/dim]")

        layout["detection_status"].update(
            Panel(det_table, title="[bold magenta]DETECTION STATUS[/bold magenta]", border_style="magenta")
        )

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
            "[bold magenta]Q[/bold magenta] = Quit"
        )
        layout["footer"].update(Panel(footer_text, style="dim"))

        return layout

    def run(self, max_seconds: Optional[float] = None) -> None:
        """Run the live terminal interface loop."""
        self._is_running = True
        self.engine.start()

        is_tty = sys.stdin.isatty()
        old_settings = None
        if is_tty:
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
                    if is_tty and select.select([sys.stdin], [], [], 0.0)[0]:
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
                        except Exception:
                            pass

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
    cfg = HardwareConfig()
    # Check if physical devices are present
    from aetherhound.hardware.device_check import run_diagnostics
    diag = run_diagnostics(cfg)

    # If physical devices missing, enable synthetic fallback to allow terminal demonstration
    engine = RealtimeEngine(
        config=cfg,
        synthetic_rf=not diag.sdr_device.connected,
        synthetic_audio=not diag.mic_device.connected,
    )
    monitor = LiveMonitorInterface(engine)
    print("Launching AetherHound Live Terminal Monitor...")
    monitor.run()
