"""
Real-Time Autoencoder Inference & Anomaly Scoring Engine.
Computes reconstruction errors on streaming spectrogram patches,
maintains adaptive statistical thresholds, and generates alert triggers.
"""

import os
import torch
import numpy as np
from typing import Dict, Any, Tuple, Optional
from aetherhound.ml.autoencoder import SpectralAutoencoder
from aetherhound.config import MLAutoencoderConfig

class AnomalyEvaluator:
    """
    Evaluator for streaming anomaly detection using trained PyTorch Autoencoder.
    Employs dynamic adaptive thresholding (Mean + k * StdDev).
    """

    def __init__(self, model_path: Optional[str] = None, config: Optional[MLAutoencoderConfig] = None, device: str = "cpu"):
        self.config = config or MLAutoencoderConfig()
        self.device = torch.device(device)
        self.model = SpectralAutoencoder(latent_dim=self.config.latent_dim).to(self.device)
        self.model_loaded = False

        path = model_path or self.config.model_save_path
        if os.path.exists(path):
            try:
                state_dict = torch.load(path, map_location=self.device, weights_only=True)
                self.model.load_state_dict(state_dict)
                self.model_loaded = True
            except Exception as e:
                # If loading fails or weights_only flag issue, fallback cleanly
                try:
                    state_dict = torch.load(path, map_location=self.device)
                    self.model.load_state_dict(state_dict)
                    self.model_loaded = True
                except Exception:
                    self.model_loaded = False
        self.model.eval()

        # Dynamic Threshold Statistics (Welford's algorithm / rolling window)
        self.threshold_k = self.config.anomaly_threshold_std_multiplier
        self.baseline_errors = []
        self.baseline_mean = 0.005
        self.baseline_std = 0.0015
        self.threshold = self.baseline_mean + self.threshold_k * self.baseline_std

    def calibrate_baseline(self, baseline_patches: np.ndarray) -> Dict[str, float]:
        """
        Calibrate baseline statistical distribution on known normal server hum.
        """
        self.model.eval()
        errors = []
        with torch.no_grad():
            for patch in baseline_patches:
                t_patch = torch.from_numpy(patch).unsqueeze(0).unsqueeze(0).to(self.device)
                recon, _ = self.model(t_patch)
                residual = (recon - t_patch) ** 2
                loss = torch.mean(residual).item() + 1.5 * torch.max(residual).item()
                errors.append(loss)

        errors_arr = np.array(errors)
        self.baseline_mean = float(np.mean(errors_arr))
        self.baseline_std = float(np.std(errors_arr))
        self.threshold = self.baseline_mean + self.threshold_k * self.baseline_std
        self.baseline_errors = errors

        return {
            "baseline_mean_error": self.baseline_mean,
            "baseline_std_error": self.baseline_std,
            "calibrated_threshold": self.threshold,
            "samples_calibrated": len(baseline_patches)
        }

    def evaluate_patch(self, patch: np.ndarray) -> Dict[str, Any]:
        """
        Evaluate a single 2D spectrogram patch (40, 64).
        Returns:
            reconstruction_error: float
            threshold: float
            is_anomaly: bool
            anomaly_score: float (ratio to threshold)
            reconstruction_patch: np.ndarray
        """
        self.model.eval()
        with torch.no_grad():
            t_patch = torch.from_numpy(patch.astype(np.float32)).unsqueeze(0).unsqueeze(0).to(self.device)
            recon, _ = self.model(t_patch)
            residual = (recon - t_patch) ** 2
            recon_error = torch.mean(residual).item() + 1.5 * torch.max(residual).item()

            recon_np = recon.squeeze().cpu().numpy()

        is_anomaly = recon_error > self.threshold
        anomaly_score = recon_error / (self.threshold + 1e-8)

        # Update running baseline stats gently if NOT anomalous to track slow thermal drifts
        if not is_anomaly:
            alpha = 0.01  # Slow exponential moving average
            self.baseline_mean = (1 - alpha) * self.baseline_mean + alpha * recon_error

        return {
            "reconstruction_error": float(recon_error),
            "threshold": float(self.threshold),
            "is_anomaly": bool(is_anomaly),
            "anomaly_score": float(anomaly_score),
            "reconstructed_patch": recon_np
        }
