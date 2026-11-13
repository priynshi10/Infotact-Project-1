"""
Machine Learning Model Evaluation Metrics & Visualization Suite.
Calculates ROC curves, AUC, Precision-Recall, Confusion Matrices,
and exports high-resolution engineering figures into evaluation_results/.
"""

import os
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Headless backend
import matplotlib.pyplot as plt
from sklearn.metrics import (
    roc_curve,
    auc,
    precision_recall_curve,
    average_precision_score,
    confusion_matrix,
    classification_report
)
from typing import Dict, Any, Tuple

class ModelEvaluatorMetrics:
    """
    Computes rigorous ML classification and SIGINT detection metrics.
    Generates academic/industrial evaluation charts.
    """

    def __init__(self, output_dir: str = "evaluation_results"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def evaluate_and_plot_all(
        self,
        y_true: np.ndarray,
        reconstruction_errors: np.ndarray,
        threshold: float,
        normal_patch: np.ndarray,
        attack_patch: np.ndarray,
        attack_recon: np.ndarray
    ) -> Dict[str, Any]:
        """
        Run full evaluation pipeline and save visual figure artifacts.
        """
        y_pred = (reconstruction_errors > threshold).astype(int)

        # 1. ROC Curve & AUC
        fpr, tpr, _ = roc_curve(y_true, reconstruction_errors)
        roc_auc = float(auc(fpr, tpr))

        # 2. Precision-Recall Curve & Average Precision
        prec, rec, _ = precision_recall_curve(y_true, reconstruction_errors)
        pr_auc = float(average_precision_score(y_true, reconstruction_errors))

        # 3. Confusion Matrix
        cm = confusion_matrix(y_true, y_pred)
        tn, fp, fn, tp = cm.ravel()

        accuracy = float((tp + tn) / len(y_true))
        precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = float(2 * (precision * recall) / (precision + recall + 1e-12))
        fpr_rate = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0

        # Save Plots
        self._plot_roc_curve(fpr, tpr, roc_auc)
        self._plot_precision_recall_curve(rec, prec, pr_auc)
        self._plot_error_distribution(y_true, reconstruction_errors, threshold)
        self._plot_confusion_matrix(cm)
        self._plot_spectrogram_anomaly(normal_patch, attack_patch, attack_recon)

        metrics_summary = {
            "roc_auc": round(roc_auc, 4),
            "pr_auc": round(pr_auc, 4),
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "false_positive_rate": round(fpr_rate, 4),
            "optimal_threshold": round(float(threshold), 6),
            "total_test_samples": len(y_true),
            "true_positives": int(tp),
            "false_positives": int(fp),
            "true_negatives": int(tn),
            "false_negatives": int(fn)
        }

        with open(os.path.join(self.output_dir, "metrics_summary.json"), "w") as f:
            json.dump(metrics_summary, f, indent=4)

        return metrics_summary

    def _plot_roc_curve(self, fpr: np.ndarray, tpr: np.ndarray, roc_auc: float) -> None:
        fig, ax = plt.subplots(figsize=(7, 6))
        ax.plot(fpr, tpr, color="#00ffcc", lw=2.5, label=f"AetherHound Autoencoder (AUC = {roc_auc:.4f})")
        ax.plot([0, 1], [0, 1], color="#888888", linestyle="--", lw=1.5, label="Random Guess Baseline")
        ax.set_xlim([-0.02, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel("False Positive Rate (FPR)", fontsize=11, fontweight="bold")
        ax.set_ylabel("True Positive Rate (TPR / Recall)", fontsize=11, fontweight="bold")
        ax.set_title("AetherHound Receiver Operating Characteristic (ROC)", fontsize=13, fontweight="bold")
        ax.legend(loc="lower right", frameon=True, facecolor="#f0f0f0")
        ax.grid(True, linestyle=":", alpha=0.6)
        fig.tight_layout()
        fig.savefig(os.path.join(self.output_dir, "roc_curve.png"), dpi=300)
        plt.close(fig)

    def _plot_precision_recall_curve(self, recall: np.ndarray, precision: np.ndarray, pr_auc: float) -> None:
        fig, ax = plt.subplots(figsize=(7, 6))
        ax.plot(recall, precision, color="#ff007f", lw=2.5, label=f"PR Curve (AP = {pr_auc:.4f})")
        ax.set_xlim([0.0, 1.02])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel("Recall (Detection Sensitivity)", fontsize=11, fontweight="bold")
        ax.set_ylabel("Precision (Positive Predictive Value)", fontsize=11, fontweight="bold")
        ax.set_title("AetherHound Precision-Recall Curve", fontsize=13, fontweight="bold")
        ax.legend(loc="lower left", frameon=True, facecolor="#f0f0f0")
        ax.grid(True, linestyle=":", alpha=0.6)
        fig.tight_layout()
        fig.savefig(os.path.join(self.output_dir, "precision_recall_curve.png"), dpi=300)
        plt.close(fig)

    def _plot_error_distribution(self, y_true: np.ndarray, errors: np.ndarray, threshold: float) -> None:
        fig, ax = plt.subplots(figsize=(8, 5))
        normal_errors = errors[y_true == 0]
        malware_errors = errors[y_true == 1]

        ax.hist(normal_errors, bins=30, alpha=0.65, color="#1f77b4", label="Baseline Normal Hum", density=True)
        ax.hist(malware_errors, bins=30, alpha=0.65, color="#d62728", label="Covert Malware (Fansmitter/RAMBO)", density=True)
        ax.axvline(threshold, color="#ff9900", linestyle="--", lw=2.5, label=f"Detection Threshold ({threshold:.4f})")

        ax.set_xlabel("Reconstruction Loss (MSE)", fontsize=11, fontweight="bold")
        ax.set_ylabel("Probability Density", fontsize=11, fontweight="bold")
        ax.set_title("Reconstruction Loss Distribution: Baseline vs Covert Attack", fontsize=13, fontweight="bold")
        ax.legend(frameon=True, facecolor="#f0f0f0")
        ax.grid(True, linestyle=":", alpha=0.6)
        fig.tight_layout()
        fig.savefig(os.path.join(self.output_dir, "reconstruction_loss_distribution.png"), dpi=300)
        plt.close(fig)

    def _plot_confusion_matrix(self, cm: np.ndarray) -> None:
        fig, ax = plt.subplots(figsize=(6, 5))
        cax = ax.matshow(cm, cmap="Blues", alpha=0.85)
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax.text(j, i, str(cm[i, j]), ha="center", va="center", color="black" if cm[i, j] < cm.max()/2 else "white", fontsize=14, fontweight="bold")
        fig.colorbar(cax)
        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xticklabels(["Baseline (0)", "Covert Channel (1)"], fontsize=10)
        ax.set_yticklabels(["Baseline (0)", "Covert Channel (1)"], fontsize=10)
        ax.set_xlabel("Predicted Label", fontsize=11, fontweight="bold")
        ax.set_ylabel("True Label", fontsize=11, fontweight="bold")
        ax.set_title("Confusion Matrix", fontsize=13, fontweight="bold", pad=20)
        fig.tight_layout()
        fig.savefig(os.path.join(self.output_dir, "confusion_matrix.png"), dpi=300)
        plt.close(fig)

    def _plot_spectrogram_anomaly(self, normal_patch: np.ndarray, attack_patch: np.ndarray, attack_recon: np.ndarray) -> None:
        fig, axes = plt.subplots(1, 3, figsize=(14, 4))

        im0 = axes[0].imshow(normal_patch, aspect="auto", cmap="viridis", origin="lower")
        axes[0].set_title("Baseline Normal Server Hum", fontsize=11, fontweight="bold")
        axes[0].set_xlabel("Frequency Bins")
        axes[0].set_ylabel("Time Slices")
        fig.colorbar(im0, ax=axes[0])

        im1 = axes[1].imshow(attack_patch, aspect="auto", cmap="magma", origin="lower")
        axes[1].set_title("Covert Channel Injected (Fansmitter)", fontsize=11, fontweight="bold")
        axes[1].set_xlabel("Frequency Bins")
        fig.colorbar(im1, ax=axes[1])

        diff = np.abs(attack_patch - attack_recon)
        im2 = axes[2].imshow(diff, aspect="auto", cmap="inferno", origin="lower")
        axes[2].set_title("Reconstruction Residual Heatmap (Flagged!)", fontsize=11, fontweight="bold", color="red")
        axes[2].set_xlabel("Frequency Bins")
        fig.colorbar(im2, ax=axes[2])

        fig.tight_layout()
        fig.savefig(os.path.join(self.output_dir, "spectrogram_anomaly_detection.png"), dpi=300)
        plt.close(fig)
