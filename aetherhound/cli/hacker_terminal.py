"""
Hacker-Style Terminal UI (Rich-based) for Air-Gapped Physical Hardware.
Runs entirely offline without web browsers, electron, or internet connections.
Displays live spectrum waterfalls, RF spikes, server room rack maps, and alert banners at 30+ FPS.
"""

import time
import sys
import numpy as np
from typing import Optional

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.live import Live

from aetherhound.engine.coordinator import PipelineCoordinator
from aetherhound.config import AetherHoundConfig, DEFAULT_CONFIG

class HackerTerminalUI:
    """
    Air-gapped tactical CLI dashboard.
    Renders high-speed ASCII waterfalls, rack maps, and telemetry gauges.
    """

    WATERFALL_CHARS = "  ░▒▓█"

    def __init__(self, coordinator: Optional[PipelineCoordinator] = None):
        self.coordinator = coordinator or PipelineCoordinator()
        self.console = Console()
        self.layout = Layout()
        self._setup_layout()

    def _setup_layout(self) -> None:
        """Create responsive grid layout."""
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=5)
        )
        self.layout["body"].split_row(
            Layout(name="waterfall_panel", ratio=3),
            Layout(name="sidebar", ratio=2)
        )
        self.layout["sidebar"].split_column(
            Layout(name="rack_map", size=10),
            Layout(name="telemetry", ratio=1),
            Layout(name="incident_log", size=7)
        )

    def _render_header(self, frame_data: dict) -> Panel:
        """Header with alert state."""
        is_anomaly = frame_data["is_anomaly"]
        fps = frame_data.get("fps", 30.0)

        if is_anomaly:
            title = Text("🚨 [CRITICAL ALERT] COVERT CHANNEL EMISSION DETECTED 🚨", style="bold white on red blink")
        else:
            title = Text("🛡️ AETHERHOUND // AIR-GAPPED RF & ACOUSTIC COVERT CHANNEL DETECTOR", style="bold green")

        sub = Text(f" Mode: AIR-GAPPED SECURE | Version: 2.4.0-HARDENED | Engine FPS: {fps:.1f} | Latency: {frame_data['cycle_latency_ms']:.1f}ms", style="dim")
        header_text = Text.assemble(title, "\n", sub)
        return Panel(header_text, style="red" if is_anomaly else "green")

    def _render_waterfall(self, frame_data: dict) -> Panel:
        """Render ASCII/Unicode spectrum waterfall."""
        waterfall = frame_data["waterfall"]  # Shape: (depth, n_bins)
        # Select active frequency window (e.g. 0 to 4000 Hz)
        n_rows, n_cols = waterfall.shape
        display_cols = 54
        display_rows = min(14, n_rows)

        # Downsample horizontally to fit terminal panel
        step = max(1, n_cols // display_cols)
        sub_matrix = waterfall[-display_rows:, ::step][:, :display_cols]

        # Normalize to character levels 0 to 4
        p_min = np.percentile(sub_matrix, 5)
        p_max = np.percentile(sub_matrix, 95) + 1e-6
        norm = np.clip((sub_matrix - p_min) / (p_max - p_min), 0.0, 1.0)
        char_indices = (norm * (len(self.WATERFALL_CHARS) - 1)).astype(int)

        lines = []
        is_anomaly = frame_data["is_anomaly"]
        for row in char_indices:
            row_str = "".join(self.WATERFALL_CHARS[idx] for idx in row)
            if is_anomaly:
                lines.append(f"[bold red]{row_str}[/bold red]")
            else:
                lines.append(f"[cyan]{row_str}[/cyan]")

        waterfall_text = "\n".join(lines)
        freq_axis = "  0 Hz ------- 1000 Hz ------- 2000 Hz ------- 3000 Hz ------- 4000 Hz"
        content = f"{waterfall_text}\n[dim]{freq_axis}[/dim]"
        return Panel(content, title="[bold]Real-Time Spectrum Waterfall (Acoustic / RF)[/bold]", border_style="cyan")

    def _render_rack_map(self, frame_data: dict) -> Panel:
        """Render server room topology with highlighted infected rack."""
        pinpointed_rack = frame_data["pinpointed_rack"]
        is_anomaly = frame_data["is_anomaly"]

        def rack_box(name: str) -> str:
            if is_anomaly and name == pinpointed_rack:
                return f"[bold white on red] [{name[:8]}] [/bold white on red]"
            return f"[green] [{name[:8]}] [/green]"

        r_alpha = rack_box("Rack-Alpha")
        r_beta  = rack_box("Rack-Beta")
        r_gamma = rack_box("Rack-Gamma")
        r_delta = rack_box("Rack-Delta")
        r_eps   = rack_box("Rack-Epsil")
        r_zeta  = rack_box("Rack-Zeta")

        map_str = f"""
┌────────────── SERVER ROOM MATRIX ─────────────┐
│  {r_alpha}  {r_beta}  {r_gamma}   │
│                                                │
│  {r_delta}  {r_eps}   {r_zeta}   │
└────────────────────────────────────────────────┘
 Target Pinpointed: [bold yellow]{pinpointed_rack}[/bold yellow] (Conf: {frame_data['pinpoint_confidence']*100:.1f}%)
        """
        return Panel(map_str.strip(), title="[bold]Spatial Triangulation Map[/bold]", border_style="yellow")

    def _render_telemetry(self, frame_data: dict) -> Panel:
        """SIGINT & ML Anomaly Telemetry."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Key", style="bold cyan")
        table.add_column("Value", style="bold white")

        err = frame_data["reconstruction_error"]
        thresh = frame_data["threshold"]
        peak_hz = frame_data["primary_peak_hz"]
        snr = frame_data["peak_snr_db"]
        entropy = frame_data["spectral_entropy"]

        err_style = "bold red" if err > thresh else "green"

        table.add_row("Autoencoder Loss (MSE):", f"[{err_style}]{err:.6f}[/{err_style}]")
        table.add_row("Adaptive Threshold (τ):", f"{thresh:.6f}")
        table.add_row("Peak Carrier Frequency:", f"{peak_hz:.1f} Hz")
        table.add_row("Peak Carrier SNR:", f"{snr:.1f} dB")
        table.add_row("Spectral Shannon Entropy:", f"{entropy:.3f}")
        table.add_row("Physical Ingestion Layer:", "Live Array / AirGap-Sim")

        return Panel(table, title="[bold]Neural SIGINT Telemetry[/bold]", border_style="magenta")

    def _render_incident_log(self, frame_data: dict) -> Panel:
        """Covert Channel Demodulated Stream."""
        demod = frame_data.get("demodulated_text", "")
        if not demod:
            demod = "STANDBY - No covert transmission detected"
            content = f"[dim]{demod}[/dim]"
        else:
            content = f"[bold yellow]DECODED PAYLOAD:[/bold yellow] [bold green on black] {demod} [/bold green on black]\n[red]Protocol: Acoustic PWM / Morse FSK (Fansmitter)[/red]"
        return Panel(content, title="[bold]SIGINT Demodulator Output[/bold]", border_style="blue")

    def _render_footer(self, frame_data: dict) -> Panel:
        """Status controls."""
        rssi_str = " | ".join([f"{k}: {v:.1f} dB" for k, v in frame_data.get("sensor_rssi", {}).items()])
        content = f"Sensor Array Array RSSI: {rssi_str}\nControls: [Ctrl+C] Exit | [M] Toggle Mock Fansmitter | [R] Toggle RAMBO RF"
        return Panel(content, style="dim")

    def run(self, max_frames: Optional[int] = None, fps_target: int = 30) -> None:
        """Main rendering loop maintaining 30+ FPS."""
        frame_interval = 1.0 / fps_target
        frame_count = 0
        t_prev = time.time()
        fps = 30.0

        with Live(self.layout, refresh_per_second=fps_target, screen=True) as live:
            while True:
                t_start = time.perf_counter()
                frame_data = self.coordinator.process_frame()

                now = time.time()
                dt = now - t_prev
                if dt > 0:
                    fps = 0.9 * fps + 0.1 * (1.0 / dt)
                t_prev = now
                frame_data["fps"] = fps

                self.layout["header"].update(self._render_header(frame_data))
                self.layout["waterfall_panel"].update(self._render_waterfall(frame_data))
                self.layout["rack_map"].update(self._render_rack_map(frame_data))
                self.layout["telemetry"].update(self._render_telemetry(frame_data))
                self.layout["incident_log"].update(self._render_incident_log(frame_data))
                self.layout["footer"].update(self._render_footer(frame_data))

                frame_count += 1
                if max_frames and frame_count >= max_frames:
                    break

                elapsed = time.perf_counter() - t_start
                sleep_time = max(0.0, frame_interval - elapsed)
                time.sleep(sleep_time)

if __name__ == "__main__":
    ui = HackerTerminalUI()
    ui.run(max_frames=100)
