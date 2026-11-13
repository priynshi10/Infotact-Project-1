"""
AetherHound Engine Package.
Coordinates triangulation, demodulation, alert handling, and master pipeline flow.
"""

try:
    from aetherhound.engine.alert_manager import AlertManager, IncidentReport
except ImportError:
    AlertManager = None
    IncidentReport = None

try:
    from aetherhound.engine.triangulator import RackTriangulator
except ImportError:
    RackTriangulator = None

try:
    from aetherhound.engine.demodulator import CovertChannelDemodulator
except ImportError:
    CovertChannelDemodulator = None

try:
    from aetherhound.engine.coordinator import PipelineCoordinator
except ImportError:
    PipelineCoordinator = None

__all__ = [
    "AlertManager",
    "IncidentReport",
    "RackTriangulator",
    "CovertChannelDemodulator",
    "PipelineCoordinator",
]
