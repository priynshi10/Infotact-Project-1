"""
AetherHound Digital Signal Processing (DSP) Package.
Provides spectral analysis, digital filtering, and accelerated matrix math.
"""

from aetherhound.dsp.filters import SignalFilter
from aetherhound.dsp.spectral import SpectralAnalyzer
from aetherhound.dsp.detector_dsp import SignalFeatureDetector
from aetherhound.dsp.accelerated_dsp import AcceleratedDSPEngine

__all__ = [
    "SignalFilter",
    "SpectralAnalyzer",
    "SignalFeatureDetector",
    "AcceleratedDSPEngine",
]
