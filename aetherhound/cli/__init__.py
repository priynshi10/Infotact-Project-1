"""
AetherHound Command Line Interface (CLI) Package.
Provides Rich and Curses dashboards for air-gapped monitoring.
"""

from aetherhound.cli.hacker_terminal import HackerTerminalUI
from aetherhound.cli.curses_ui import CursesEdgeDashboard

__all__ = [
    "HackerTerminalUI",
    "CursesEdgeDashboard",
]
