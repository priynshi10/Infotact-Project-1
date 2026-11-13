"""
Dataset & Spectrogram Generator for PyTorch Autoencoder Training.
Provides data loaders, augmentations, and synthetic dataset generation
for baseline server room emissions and covert channel attacks.
"""

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from typing import Tuple, List, Optional
from aetherhound.sensors.emulator import AirGapEnvironmentEmulator
from aetherhound.dsp.spectral import SpectralAnalyzer
from aetherhound.config import DEFAULT_CONFIG

class SpectrogramPatchDataset(Dataset):
    """
    PyTorch Dataset of 2D Spectrogram Patches (Shape: 1, 40, 64).
    Supports on-the-fly data augmentation to prevent false positives.
    """

    def __init__(self, patches: np.ndarray, labels: Optional[np.ndarray] = None, augment: bool = False):
        """
        patches: np.ndarray of shape (N, 40, 64)
        labels: np.ndarray of shape (N,) (0: Normal Baseline, 1: Covert Channel Attack)
        """
        self.patches = patches.astype(np.float32)
        self.labels = labels.astype(np.int64) if labels is not None else np.zeros(len(patches), dtype=np.int64)
        self.augment = augment

    def __len__(self) -> int:
        return len(self.patches)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        patch = self.patches[idx].copy()

        if self.augment:
            # Data Augmentation: Random gain scaling (0.9 to 1.1)
            gain = np.random.uniform(0.9, 1.1)
            patch = patch * gain
            # Additive low-level Gaussian room jitter
            noise = np.random.normal(0, 0.02, patch.shape).astype(np.float32)
            patch = np.clip(patch + noise, 0.0, 1.0)

        # Add channel dimension: (1, 40, 64)
        tensor_patch = torch.from_numpy(patch).unsqueeze(0)
        tensor_label = torch.tensor(self.labels[idx], dtype=torch.long)
        return tensor_patch, tensor_label

def generate_training_data(n_samples: int = 600, patch_shape: Tuple[int, int] = (40, 64)) -> np.ndarray:
    """
    Generate unsupervised baseline server room training data (normal hum).
    """
    emulator = AirGapEnvironmentEmulator()
    analyzer = SpectralAnalyzer(sample_rate=DEFAULT_CONFIG.acoustic.sample_rate)

    patches = []
    chunk_size = 4096

    for _ in range(n_samples):
        # Read normal baseline server hum (Fansmitter inactive)
        audio_array, _ = emulator.generate_multichannel_acoustic(chunk_size)
        primary_audio = audio_array[0]
        patch = analyzer.compute_spectrogram_patch(primary_audio, target_shape=patch_shape)
        patches.append(patch)

    return np.array(patches, dtype=np.float32)

def generate_evaluation_benchmark_data(n_samples: int = 400, attack_ratio: float = 0.5) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate labeled test dataset containing both normal baseline emissions (0)
    and mock covert channel attacks (1: Fansmitter / RAMBO).
    """
    emulator = AirGapEnvironmentEmulator()
    analyzer = SpectralAnalyzer(sample_rate=DEFAULT_CONFIG.acoustic.sample_rate)

    patches = []
    labels = []
    chunk_size = 4096

    n_attacks = int(n_samples * attack_ratio)
    n_normals = n_samples - n_attacks

    # 1. Normal baseline samples
    for _ in range(n_normals):
        emulator.set_fansmitter_state(active=False)
        emulator.set_rambo_state(active=False)
        audio_array, _ = emulator.generate_multichannel_acoustic(chunk_size)
        patch = analyzer.compute_spectrogram_patch(audio_array[0])
        patches.append(patch)
        labels.append(0)

    # 2. Covert Malware Attack samples (Fansmitter acoustic PWM tones)
    for _ in range(n_attacks):
        freq = float(np.random.choice([1800.0, 1950.0, 2200.0, 2400.0]))
        rack = str(np.random.choice(["Rack-Delta", "Rack-Beta", "Rack-Alpha", "Rack-Gamma"]))
        emulator.set_fansmitter_state(active=True, rack=rack, freq_hz=freq)
        audio_array, _ = emulator.generate_multichannel_acoustic(chunk_size)
        patch = analyzer.compute_spectrogram_patch(audio_array[0])
        patches.append(patch)
        labels.append(1)

    return np.array(patches, dtype=np.float32), np.array(labels, dtype=np.int64)
