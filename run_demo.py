"""
AetherHound Turnkey Demonstration Runner.
Demonstrates the complete physical SIGINT detection workflow:
1. Baseline server room acoustic & RF hum monitoring.
2. Mock malware injection (Fansmitter CPU fan modulation).
3. Real-time DSP frequency spike isolation & waterfall rendering.
4. PyTorch Autoencoder anomaly detection & red alert trigger.
5. Multi-sensor spatial triangulation pinpointing the infected server rack.
6. Demodulation of the intercepted secret payload.
"""

import sys
import time
import argparse

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from aetherhound.engine.coordinator import PipelineCoordinator
from aetherhound.cli.hacker_terminal import HackerTerminalUI

def run_interactive_terminal_demo(fps: int = 30, total_frames: int = 150):
    """Launch full Rich terminal UI with automated malware injection at frame 50."""
    console = Console()
    console.print("\n[bold cyan]================================================================[/bold cyan]")
    console.print("[bold green]  STARTING AETHERHOUND TACTICAL SIGINT MONITORING ENGINE[/bold green]")
    console.print("[bold cyan]================================================================[/bold cyan]\n")

    coordinator = PipelineCoordinator()
    ui = HackerTerminalUI(coordinator)

    # Automatically trigger malware at frame 40, stop at frame 110
    class AutoDemoTerminal(HackerTerminalUI):
        def run_automated(self, max_frames: int = 150):
            frame_interval = 1.0 / 30.0
            frame_count = 0
            t_prev = time.time()
            fps_val = 30.0

            from rich.live import Live
            with Live(self.layout, refresh_per_second=30, screen=True) as live:
                while frame_count < max_frames:
                    t_start = time.perf_counter()

                    # Automated scenario injection
                    if frame_count == 35:
                        self.coordinator.emulator.set_fansmitter_state(active=True, rack="Rack-Delta", freq_hz=1950.0)
                    elif frame_count == 115:
                        self.coordinator.emulator.set_fansmitter_state(active=False)

                    frame_data = self.coordinator.process_frame()

                    now = time.time()
                    dt = now - t_prev
                    if dt > 0:
                        fps_val = 0.9 * fps_val + 0.1 * (1.0 / dt)
                    t_prev = now
                    frame_data["fps"] = fps_val

                    self.layout["header"].update(self._render_header(frame_data))
                    self.layout["waterfall_panel"].update(self._render_waterfall(frame_data))
                    self.layout["rack_map"].update(self._render_rack_map(frame_data))
                    self.layout["telemetry"].update(self._render_telemetry(frame_data))
                    self.layout["incident_log"].update(self._render_incident_log(frame_data))
                    self.layout["footer"].update(self._render_footer(frame_data))

                    frame_count += 1
                    elapsed = time.perf_counter() - t_start
                    time.sleep(max(0.0, frame_interval - elapsed))

    demo_app = AutoDemoTerminal(coordinator)
    demo_app.run_automated(max_frames=total_frames)

    # Post-demo summary
    console.print("\n[bold green][OK] Demonstration Completed Successfully.[/bold green]")
    console.print(f"Total Incidents Dispatched: [bold yellow]{len(coordinator.alert_manager.incident_history)}[/bold yellow]")
    if coordinator.alert_manager.incident_history:
        latest = coordinator.alert_manager.incident_history[-1]
        console.print(f"Last Incident ID: [cyan]{latest.incident_id}[/cyan]")
        console.print(f"Target Rack Pinpointed: [bold red]{latest.pinpointed_rack}[/bold red] (Confidence: {latest.confidence_score*100:.1f}%)")
        console.print(f"Intercepted Payload: [bold green]{latest.demodulated_payload}[/bold green]")
        console.print(f"Audit Log Written to: [dim]{coordinator.config.alerting.incident_log_file}[/dim]\n")

def run_headless_audit_demo():
    """Run non-interactive audit script suitable for CI/CD and terminal logging."""
    console = Console()
    console.print("\n[bold cyan]================================================================[/bold cyan]")
    console.print("[bold green]  AETHERHOUND SIGINT CAPTURE & AUDIT DEMONSTRATION (HEADLESS)[/bold green]")
    console.print("[bold cyan]================================================================[/bold cyan]\n")

    coordinator = PipelineCoordinator()

    table = Table(title="Live Telemetry Log (Sampled Frames)", border_style="cyan")
    table.add_column("Frame", justify="right", style="cyan")
    table.add_column("State", style="bold")
    table.add_column("Recon Loss", justify="right")
    table.add_column("Threshold", justify="right")
    table.add_column("Peak Freq", justify="right")
    table.add_column("SNR (dB)", justify="right")
    table.add_column("Pinpointed Rack", style="bold yellow")
    table.add_column("Demodulated Text", style="green")

    # 1. Normal Baseline Phase
    console.print("[*] Stage 1: Monitoring Normal Server Room Baseline Hum (Frames 1-10)...")
    for i in range(1, 11):
        f = coordinator.process_frame()
        if i % 3 == 0:
            table.add_row(
                str(f["frame_index"]),
                "[green]NORMAL[/green]",
                f"{f['reconstruction_error']:.6f}",
                f"{f['threshold']:.6f}",
                f"{f['primary_peak_hz']:.1f} Hz",
                f"{f['peak_snr_db']:.1f} dB",
                f["pinpointed_rack"],
                "-"
            )

    # 2. Covert Channel Attack Phase
    console.print("[*] Stage 2: INJECTING COVERT MALWARE (Fansmitter at Rack-Delta, 1950 Hz)...")
    coordinator.emulator.set_fansmitter_state(active=True, rack="Rack-Delta", freq_hz=1950.0)

    for i in range(11, 21):
        f = coordinator.process_frame()
        state = "[bold red]ANOMALY[/bold red]" if f["is_anomaly"] else "[green]NORMAL[/green]"
        if i % 2 == 0 or f["is_anomaly"]:
            table.add_row(
                str(f["frame_index"]),
                state,
                f"{f['reconstruction_error']:.6f}",
                f"{f['threshold']:.6f}",
                f"{f['primary_peak_hz']:.1f} Hz",
                f"{f['peak_snr_db']:.1f} dB",
                f"[bold red]{f['pinpointed_rack']}[/bold red]",
                f["demodulated_text"] or "-"
            )

    console.print(table)
    console.print("\n[bold green][OK] Headless demonstration completed successfully.[/bold green]\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AetherHound Demonstration Runner")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive Rich terminal UI")
    parser.add_argument("--frames", type=int, default=100, help="Total frames to simulate")
    args = parser.parse_args()

    if args.interactive:
        run_interactive_terminal_demo(total_frames=args.frames)
    else:
        run_headless_audit_demo()
