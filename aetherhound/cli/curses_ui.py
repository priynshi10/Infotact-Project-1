"""
Native Python Curses CLI Dashboard for Headless Linux / Raspberry Pi Deployments.
Provides ultra-lightweight terminal interface without external graphics or browser engines.
"""

import time
try:
    import curses
except ImportError:
    curses = None
import numpy as np
from typing import Optional
from aetherhound.engine.coordinator import PipelineCoordinator

class CursesEdgeDashboard:
    """
    Lightweight Curses dashboard for embedded ARM/Raspberry Pi hardware.
    """

    def __init__(self, coordinator: Optional[PipelineCoordinator] = None):
        self.coordinator = coordinator or PipelineCoordinator()

    def _draw_dashboard(self, stdscr) -> None:
        curses.curs_set(0)
        stdscr.nodelay(True)
        curses.start_color()
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)

        frame_count = 0
        while True:
            key = stdscr.getch()
            if key == ord('q') or key == 27:  # Esc or 'q'
                break
            elif key == ord('m'):
                # Toggle mock malware
                curr = self.coordinator.emulator.fansmitter_active
                self.coordinator.emulator.set_fansmitter_state(not curr)

            frame = self.coordinator.process_frame()
            is_anomaly = frame["is_anomaly"]

            stdscr.erase()
            # Title
            if is_anomaly:
                stdscr.attron(curses.color_pair(2) | curses.A_BOLD | curses.A_BLINK)
                stdscr.addstr(0, 2, ">>> [ALERT] AIR-GAP COVERT CHANNEL ACTIVE <<<")
                stdscr.attroff(curses.color_pair(2) | curses.A_BOLD | curses.A_BLINK)
            else:
                stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
                stdscr.addstr(0, 2, "=== AETHERHOUND // AIR-GAP RF & ACOUSTIC MONITOR ===")
                stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)

            # Telemetry
            stdscr.attron(curses.color_pair(3))
            stdscr.addstr(2, 2, f"Recon Loss: {frame['reconstruction_error']:.6f} | Thresh: {frame['threshold']:.6f}")
            stdscr.addstr(3, 2, f"Peak Freq:  {frame['primary_peak_hz']:.1f} Hz | Peak SNR: {frame['peak_snr_db']:.1f} dB")
            stdscr.addstr(4, 2, f"Target:     {frame['pinpointed_rack']} (Conf: {frame['pinpoint_confidence']*100:.1f}%)")
            stdscr.attroff(curses.color_pair(3))

            # Demodulated payload
            demod = frame.get("demodulated_text", "")
            if demod:
                stdscr.attron(curses.color_pair(4) | curses.A_BOLD)
                stdscr.addstr(6, 2, f"Demodulated Payload: {demod}")
                stdscr.attroff(curses.color_pair(4) | curses.A_BOLD)

            stdscr.addstr(8, 2, "Press 'q' to exit, 'm' to toggle Fansmitter attack")
            stdscr.refresh()
            time.sleep(0.033)  # ~30 FPS

    def run(self) -> None:
        curses.wrapper(self._draw_dashboard)

if __name__ == "__main__":
    app = CursesEdgeDashboard()
    app.run()
