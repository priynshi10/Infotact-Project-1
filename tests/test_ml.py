"""
Unit Tests for AetherHound PyTorch Machine Learning Pipeline.
"""

import os
import torch
import numpy as np
import pytest
from aetherhound.ml.autoencoder import SpectralAutoencoder
from aetherhound.ml.dataset import SpectrogramPatchDataset
from aetherhound.ml.evaluator import AnomalyEvaluator

def test_spectral_autoencoder_dimensions():
    model = SpectralAutoencoder(latent_dim=32)
    # Input batch: (B=4, C=1, T=40, F=64)
    x = torch.randn(4, 1, 40, 64)
    recon, z = model(x)
    assert z.shape == (4, 32)
    assert recon.shape == (4, 1, 40, 64)
    loss = model.compute_loss(x, recon)
    assert loss.item() > 0.0

def test_spectrogram_dataset():
    dummy_patches = np.random.rand(10, 40, 64).astype(np.float32)
    labels = np.array([0, 1] * 5)
    dataset = SpectrogramPatchDataset(dummy_patches, labels, augment=True)
    assert len(dataset) == 10
    patch_t, label_t = dataset[0]
    assert patch_t.shape == (1, 40, 64)
    assert label_t.item() in (0, 1)

def test_anomaly_evaluator():
    evaluator = AnomalyEvaluator()
    dummy_baseline = np.random.rand(20, 40, 64).astype(np.float32) * 0.3
    calib = evaluator.calibrate_baseline(dummy_baseline)
    assert "calibrated_threshold" in calib
    assert calib["calibrated_threshold"] > 0.0

    # Evaluate normal patch
    norm_res = evaluator.evaluate_patch(dummy_baseline[0])
    assert "reconstruction_error" in norm_res
    assert "is_anomaly" in norm_res
