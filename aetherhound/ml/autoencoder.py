"""
PyTorch Deep Spectral Autoencoder for Covert Channel Anomaly Detection.
Trained exclusively on baseline server room electromagnetic and acoustic emissions.
Anomalous structured malware transmissions (Fansmitter/RAMBO) yield high reconstruction error.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Dict, Any

class SpectralAutoencoder(nn.Module):
    """
    Convolutional-Recurrent Neural Network Autoencoder.
    Input shape: (Batch, 1, Time_slices=40, Freq_bins=64)
    Output shape: (Batch, 1, Time_slices=40, Freq_bins=64)
    """

    def __init__(self, latent_dim: int = 32):
        super().__init__()
        self.latent_dim = latent_dim

        # Encoder Architecture
        self.encoder_conv = nn.Sequential(
            # Layer 1: (B, 1, 40, 64) -> (B, 16, 20, 32)
            nn.Conv2d(1, 16, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(16),
            nn.LeakyReLU(0.2, inplace=True),

            # Layer 2: (B, 16, 20, 32) -> (B, 32, 10, 16)
            nn.Conv2d(16, 32, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(32),
            nn.LeakyReLU(0.2, inplace=True),

            # Layer 3: (B, 32, 10, 16) -> (B, 64, 5, 8)
            nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(64),
            nn.LeakyReLU(0.2, inplace=True)
        )

        self.flatten_dim = 64 * 5 * 8  # 2560
        self.fc_latent = nn.Linear(self.flatten_dim, latent_dim)

        # Decoder Architecture
        self.fc_unflatten = nn.Linear(latent_dim, self.flatten_dim)

        self.decoder_conv = nn.Sequential(
            # Layer 1: (B, 64, 5, 8) -> (B, 32, 10, 16)
            nn.ConvTranspose2d(64, 32, kernel_size=3, stride=2, padding=1, output_padding=1),
            nn.BatchNorm2d(32),
            nn.LeakyReLU(0.2, inplace=True),

            # Layer 2: (B, 32, 10, 16) -> (B, 16, 20, 32)
            nn.ConvTranspose2d(32, 16, kernel_size=3, stride=2, padding=1, output_padding=1),
            nn.BatchNorm2d(16),
            nn.LeakyReLU(0.2, inplace=True),

            # Layer 3: (B, 16, 20, 32) -> (B, 1, 40, 64)
            nn.ConvTranspose2d(16, 1, kernel_size=3, stride=2, padding=1, output_padding=1),
            nn.Sigmoid()  # Reconstruct normalized power in [0, 1]
        )

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        """Encode spectrogram into compressed latent space."""
        h = self.encoder_conv(x)
        h_flat = h.view(h.size(0), -1)
        z = self.fc_latent(h_flat)
        return z

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        """Reconstruct spectrogram from latent vector."""
        h_flat = self.fc_unflatten(z)
        h = h_flat.view(h_flat.size(0), 64, 5, 8)
        reconstruction = self.decoder_conv(h)
        return reconstruction

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass returning: (reconstruction, latent_z)
        """
        z = self.encode(x)
        reconstruction = self.decode(z)
        return reconstruction, z

    def compute_loss(self, x: torch.Tensor, reconstruction: torch.Tensor) -> torch.Tensor:
        """
        Combined loss: Pixel-wise MSE + Frequency Gradient / Spectral Loss.
        """
        mse_loss = F.mse_loss(reconstruction, x)
        # Spectral smoothness / gradient loss along frequency axis
        grad_orig = torch.diff(x, dim=-1)
        grad_recon = torch.diff(reconstruction, dim=-1)
        grad_loss = F.mse_loss(grad_recon, grad_orig)
        return mse_loss + 0.3 * grad_loss
