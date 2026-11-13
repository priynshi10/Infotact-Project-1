"""
AetherHound Autoencoder Training & Evaluation Script.
Trains the deep spectral convolutional autoencoder on baseline server room hum,
calibrates statistical anomaly thresholds, benchmarks detection accuracy on mock covert channels,
and exports all evaluation figures and weights into evaluation_results/.
"""

import os
import sys
import time
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import numpy as np

# Ensure Windows terminal handles UTF-8 gracefully
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from aetherhound.config import DEFAULT_CONFIG
from aetherhound.ml.autoencoder import SpectralAutoencoder
from aetherhound.ml.dataset import (
    SpectrogramPatchDataset,
    generate_training_data,
    generate_evaluation_benchmark_data,
)
from aetherhound.ml.evaluator import AnomalyEvaluator
from aetherhound.ml.metrics import ModelEvaluatorMetrics

def main():
    print("=" * 70)
    print(" AETHERHOUND: SPECTRAL AUTOENCODER TRAINING & EVALUATION PIPELINE")
    print("=" * 70)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Compute Device: {device}")

    out_dir = "evaluation_results"
    os.makedirs(out_dir, exist_ok=True)
    weights_path = os.path.join(out_dir, "autoencoder_best.pt")

    # Step 1: Synthesize Unsupervised Baseline Training Data (Normal Server Hum)
    print("\n[+] Generating baseline server hum training dataset...")
    n_train_samples = 400
    train_patches = generate_training_data(n_samples=n_train_samples)
    print(f"[OK] Generated {len(train_patches)} spectrogram training patches of shape {train_patches[0].shape}")

    dataset = SpectrogramPatchDataset(train_patches, augment=True)
    dataloader = DataLoader(dataset, batch_size=32, shuffle=True)

    # Step 2: Initialize Neural Network
    model = SpectralAutoencoder(latent_dim=32).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=20)

    print("\n[+] Training Spectral Autoencoder on Baseline Emissions...")
    epochs = 20
    model.train()
    for epoch in range(1, epochs + 1):
        epoch_loss = 0.0
        for batch_x, _ in dataloader:
            batch_x = batch_x.to(device)
            optimizer.zero_grad()
            recon, _ = model(batch_x)
            loss = model.compute_loss(batch_x, recon)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * len(batch_x)

        scheduler.step()
        avg_loss = epoch_loss / len(train_patches)
        if epoch % 5 == 0 or epoch == 1:
            print(f"    Epoch [{epoch:02d}/{epochs:02d}] - Reconstruction Loss: {avg_loss:.6f}")

    # Save trained weights
    torch.save(model.state_dict(), weights_path)
    print(f"[OK] Model weights successfully exported to: {weights_path}")

    # Step 3: Calibrate Baseline Anomaly Threshold
    print("\n[+] Calibrating statistical baseline anomaly threshold (Mean + 3.5 * StdDev)...")
    evaluator = AnomalyEvaluator(model_path=weights_path, device=str(device))
    calib_stats = evaluator.calibrate_baseline(train_patches[:150])
    threshold = calib_stats["calibrated_threshold"]
    print(f"[OK] Calibrated Threshold: {threshold:.6f} (Mean: {calib_stats['baseline_mean_error']:.6f}, Std: {calib_stats['baseline_std_error']:.6f})")

    # Step 4: Generate Labeled Test Dataset (Baseline + Covert Channels)
    print("\n[+] Generating labeled evaluation dataset (Normal Server Hum vs Fansmitter/RAMBO Attacks)...")
    test_patches, test_labels = generate_evaluation_benchmark_data(n_samples=250, attack_ratio=0.5)

    print("[+] Evaluating detection metrics and reconstruction errors on test dataset...")
    reconstruction_errors = []
    sample_attack_patch = None
    sample_attack_recon = None
    sample_normal_patch = None

    for i in range(len(test_patches)):
        patch = test_patches[i]
        res = evaluator.evaluate_patch(patch)
        reconstruction_errors.append(res["reconstruction_error"])

        if test_labels[i] == 1 and sample_attack_patch is None:
            sample_attack_patch = patch
            sample_attack_recon = res["reconstructed_patch"]
        elif test_labels[i] == 0 and sample_normal_patch is None:
            sample_normal_patch = patch

    reconstruction_errors = np.array(reconstruction_errors)

    # Step 5: Compute Metrics & Save Figures
    print("\n[+] Computing ROC, AUC, Precision-Recall, Confusion Matrix and generating charts...")
    metrics_calc = ModelEvaluatorMetrics(output_dir=out_dir)
    summary = metrics_calc.evaluate_and_plot_all(
        y_true=test_labels,
        reconstruction_errors=reconstruction_errors,
        threshold=threshold,
        normal_patch=sample_normal_patch,
        attack_patch=sample_attack_patch,
        attack_recon=sample_attack_recon
    )

    print("\n" + "=" * 50)
    print(" AETHERHOUND MODEL BENCHMARK RESULTS")
    print("=" * 50)
    for k, v in summary.items():
        print(f"  {k:25s}: {v}")
    print("=" * 50)
    print(f"[OK] Visual plots saved to: {out_dir}/")
    print("  * roc_curve.png")
    print("  * precision_recall_curve.png")
    print("  * reconstruction_loss_distribution.png")
    print("  * confusion_matrix.png")
    print("  * spectrogram_anomaly_detection.png")
    print("  * metrics_summary.json")

if __name__ == "__main__":
    main()
