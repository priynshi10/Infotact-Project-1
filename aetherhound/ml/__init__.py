"""
AetherHound Machine Learning Package.
Provides PyTorch Autoencoder models, dataset pipelines, evaluators, and metrics.
"""

from aetherhound.ml.autoencoder import SpectralAutoencoder
from aetherhound.ml.dataset import (
    SpectrogramPatchDataset,
    generate_training_data,
    generate_evaluation_benchmark_data,
)
from aetherhound.ml.evaluator import AnomalyEvaluator
from aetherhound.ml.metrics import ModelEvaluatorMetrics

__all__ = [
    "SpectralAutoencoder",
    "SpectrogramPatchDataset",
    "generate_training_data",
    "generate_evaluation_benchmark_data",
    "AnomalyEvaluator",
    "ModelEvaluatorMetrics",
]
