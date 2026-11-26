"""Offline NumPy/PyTorch anomaly detector with a safe NumPy baseline fallback."""

from dataclasses import asdict, dataclass
import json
import os
from typing import Dict, Iterable, Optional, Tuple

import numpy as np
from datetime import datetime, timezone


MODEL_VERSION = "aetherhound-anomaly-v1"

FEATURE_NAMES = (
    "rms", "peak", "crest_factor", "dominant_frequency",
    "spectral_centroid", "spectral_bandwidth", "spectral_flatness",
)


def extract_numeric_features(samples: np.ndarray, sample_rate_hz: float) -> np.ndarray:
    values = np.asarray(samples)
    if values.size == 0:
        raise ValueError("Cannot extract features from an empty signal")
    if values.ndim != 1:
        raise ValueError("Feature extraction requires a one-dimensional signal")
    if not np.isfinite(sample_rate_hz) or sample_rate_hz <= 0:
        raise ValueError("Sample rate must be positive")
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("Signal contains no finite samples")

    rms = float(np.sqrt(np.mean(np.square(np.abs(values).astype(np.float64)))))
    peak = float(np.max(np.abs(values)))
    crest = float(peak / rms) if rms > 1e-12 else 0.0
    n = min(len(values), 8192)
    frame = np.abs(values[:n]).astype(np.float64)
    spectrum = np.abs(np.fft.rfft(frame * np.hanning(n)))
    freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate_hz)
    power = np.square(spectrum)
    total = float(np.sum(power))
    if total <= 1e-18:
        centroid = bandwidth = flatness = 0.0
        dominant = 0.0
    else:
        probabilities = power / total
        dominant = float(freqs[int(np.argmax(power))])
        centroid = float(np.sum(freqs * probabilities))
        bandwidth = float(np.sqrt(np.sum(np.square(freqs - centroid) * probabilities)))
        flatness = float(np.exp(np.mean(np.log(power + 1e-12))) / (np.mean(power) + 1e-12))
    result = np.array([rms, peak, crest, dominant, centroid, bandwidth, flatness], dtype=np.float64)
    if not np.all(np.isfinite(result)):
        raise ValueError("Feature extraction produced non-finite values")
    return result


def generate_synthetic_dataset(
    count_per_class: int = 100,
    seed: int = 2026,
    sample_rate_hz: float = 44100.0,
) -> Tuple[np.ndarray, np.ndarray]:
    if count_per_class < 10:
        raise ValueError("count_per_class must be at least 10")
    rng = np.random.default_rng(seed)
    normal_features = []
    anomaly_features = []
    normal_signals = []
    anomaly_signals = []
    for i in range(count_per_class):
        duration = rng.uniform(0.04, 0.12)
        n = int(duration * sample_rate_hz)
        t = np.arange(n) / sample_rate_hz
        tone = rng.uniform(300.0, 2500.0)
        noise = rng.uniform(0.01, 0.08)
        normal = 0.15 * np.sin(2 * np.pi * tone * t) + noise * rng.normal(size=n)
        normal = normal.astype(np.float64)
        normal_signals.append(normal)
        normal_features.append(extract_numeric_features(normal, sample_rate_hz))

        # Controlled injected anomaly: periodic amplitude/frequency pattern.
        amp_mod = 0.8 + 0.8 * np.sign(np.sin(2 * np.pi * rng.uniform(8, 30) * t))
        anomaly_tone = tone * rng.uniform(1.5, 3.0)
        anomaly = (0.15 * amp_mod * np.sin(2 * np.pi * anomaly_tone * t)
                   + 0.20 * rng.normal(size=n))
        anomaly = anomaly.astype(np.float64)
        anomaly_signals.append(anomaly)
        anomaly_features.append(extract_numeric_features(anomaly, sample_rate_hz))
    x = np.vstack(normal_features + anomaly_features)
    y = np.concatenate((np.zeros(count_per_class), np.ones(count_per_class))).astype(np.int8)
    return x, y


class NumPyAnomalyDetector:
    """Lightweight Mahalanobis-distance baseline; not a neural network."""

    kind = "numpy-mahalanobis"

    def __init__(self, percentile: float = 95.0):
        if not 50.0 <= percentile <= 99.9:
            raise ValueError("percentile must be between 50 and 99.9")
        self.percentile = float(percentile)
        self.mean: Optional[np.ndarray] = None
        self.inverse_cov: Optional[np.ndarray] = None
        self.threshold: Optional[float] = None

    def train(self, normal_features: np.ndarray) -> "NumPyAnomalyDetector":
        x = np.asarray(normal_features, dtype=np.float64)
        if x.ndim != 2 or x.shape[0] < 2:
            raise ValueError("normal_features must be a 2-D array with at least two rows")
        if not np.all(np.isfinite(x)):
            raise ValueError("normal_features contain NaN or Inf")
        self._raw_mean = np.mean(x, axis=0)
        std = np.std(x, axis=0)
        std = np.where(std > 1e-12, std, 1.0)
        z = (x - self._raw_mean) / std
        cov = np.cov(z, rowvar=False)
        if np.ndim(cov) == 0:
            cov = np.array([[cov]])
        cov += np.eye(cov.shape[0]) * 1e-6
        self.inverse_cov = np.linalg.pinv(cov)
        self.mean = np.mean(z, axis=0)
        scores = self._score_matrix(z)
        self.threshold = float(np.percentile(scores, self.percentile))
        self._std = std
        return self

    def _score_matrix(self, z: np.ndarray) -> np.ndarray:
        delta = z - self.mean
        return np.sqrt(np.einsum("ij,jk,ik->i", delta, self.inverse_cov, delta))

    def score(self, feature_vector: np.ndarray) -> float:
        if self.mean is None or self.inverse_cov is None or self.threshold is None:
            raise RuntimeError("Model is not trained")
        x = np.asarray(feature_vector, dtype=np.float64)
        if x.shape != (len(FEATURE_NAMES),):
            raise ValueError(f"Incompatible feature vector: expected {len(FEATURE_NAMES)} values")
        if not np.all(np.isfinite(x)):
            raise ValueError("Feature vector contains NaN or Inf")
        z = (x - self._raw_mean) / self._std
        return float(np.sqrt(float(np.asarray(z - self.mean).dot(self.inverse_cov).dot(z - self.mean))))

    def save(self, directory: str) -> str:
        if self.mean is None or self.inverse_cov is None or self.threshold is None:
            raise RuntimeError("Cannot save an untrained model")
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, "anomaly_model.npz")
        np.savez(path, raw_mean=getattr(self, "_raw_mean", np.zeros(len(FEATURE_NAMES))),
                 mean=self.mean, inverse_cov=self.inverse_cov, threshold=np.array([self.threshold]),
                 std=getattr(self, "_std", np.ones(len(FEATURE_NAMES))),
                 feature_names=np.array(FEATURE_NAMES), model_version=np.array(MODEL_VERSION))
        return path

    @classmethod
    def load(cls, directory: str) -> "NumPyAnomalyDetector":
        path = os.path.join(directory, "anomaly_model.npz")
        if not os.path.isfile(path):
            raise FileNotFoundError("Model is not trained: anomaly_model.npz was not found")
        try:
            data = np.load(path, allow_pickle=False)
            if str(data["model_version"].item()) != MODEL_VERSION:
                raise ValueError("Incompatible model version")
            obj = cls()
            obj.mean = data["mean"]
            obj.inverse_cov = data["inverse_cov"]
            obj.threshold = float(data["threshold"][0])
            obj._std = data["std"]
            obj._raw_mean = data["raw_mean"]
            if tuple(data["feature_names"].tolist()) != FEATURE_NAMES:
                raise ValueError("Incompatible feature metadata")
            return obj
        except (OSError, ValueError, KeyError) as exc:
            raise ValueError(f"Corrupt or incompatible model: {exc}") from exc

    def predict(self, feature_vector: np.ndarray, source_id: str = "SYNTHETIC",
                timestamp: Optional[str] = None, signal_type: str = "ACOUSTIC",
                input_mode: str = "synthetic") -> dict:
        score = self.score(feature_vector)
        status = "ANOMALY" if score >= self.threshold else "NORMAL"
        summary = {name: float(value) for name, value in zip(FEATURE_NAMES, np.asarray(feature_vector))}
        return {
            "source_id": source_id, "timestamp": timestamp,
            "signal_type": signal_type, "anomaly_score": score,
            "threshold": self.threshold, "status": status,
            "model_version": MODEL_VERSION, "feature_summary": summary,
            "input_mode": input_mode, "detector_type": self.kind,
        }


def create_autoencoder_if_available():
    """Return a small PyTorch autoencoder class, or raise when PyTorch is unavailable."""
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError("PyTorch is not installed; using NumPyAnomalyDetector fallback") from exc

    class TorchAutoencoder(nn.Module):
        def __init__(self, input_size: int = len(FEATURE_NAMES), hidden_size: int = 4):
            super().__init__()
            self.encoder = nn.Sequential(
                nn.Linear(input_size, hidden_size),
                nn.ReLU(),
                nn.Linear(hidden_size, 2),
            )
            self.decoder = nn.Sequential(
                nn.Linear(2, hidden_size),
                nn.ReLU(),
                nn.Linear(hidden_size, input_size),
            )

        def forward(self, values):
            return self.decoder(self.encoder(values))

    return TorchAutoencoder


def train_numpy_baseline(
    normal_features: np.ndarray,
    output_directory: str,
    percentile: float = 95.0,
) -> Tuple[NumPyAnomalyDetector, dict]:
    """Train the normal-only baseline, persist it, and return a training summary."""
    detector = NumPyAnomalyDetector(percentile=percentile)
    detector.train(normal_features)
    model_path = detector.save(output_directory)
    normal_scores = np.sqrt(np.einsum(
        "ij,jk,ik->i",
        (((np.asarray(normal_features) - detector._raw_mean) / detector._std) - detector.mean),
        detector.inverse_cov,
        (((np.asarray(normal_features) - detector._raw_mean) / detector._std) - detector.mean),
    ))
    summary = {
        "detector_type": detector.kind,
        "model_version": MODEL_VERSION,
        "model_path": os.path.abspath(model_path),
        "normal_sample_count": int(len(normal_features)),
        "threshold": float(detector.threshold),
        "threshold_method": f"normal validation {percentile:.1f}th percentile",
        "normal_score_min": float(np.min(normal_scores)),
        "normal_score_median": float(np.median(normal_scores)),
        "normal_score_max": float(np.max(normal_scores)),
    }
    return detector, summary


PYTORCH_MODEL_VERSION = "aetherhound-pytorch-autoencoder-v1"


class PyTorchAutoencoderDetector:
    """Small CPU PyTorch autoencoder trained only on normal feature rows."""

    kind = "pytorch_autoencoder"

    def __init__(self, percentile: float = 95.0, seed: int = 2026,
                 epochs: int = 30, hidden_size: int = 4, learning_rate: float = 1e-3):
        if not 50.0 <= percentile <= 99.9:
            raise ValueError("percentile must be between 50 and 99.9")
        if epochs < 1 or hidden_size < 2:
            raise ValueError("epochs and hidden_size must be positive")
        self.percentile = float(percentile)
        self.seed = int(seed)
        self.epochs = int(epochs)
        self.hidden_size = int(hidden_size)
        self.learning_rate = float(learning_rate)
        self.mean = None
        self.std = None
        self.threshold = None
        self.model = None
        self.trained = False

    def _torch_and_model(self):
        try:
            import torch
            from torch import nn
        except ImportError as exc:
            raise RuntimeError("PyTorch is not installed") from exc

        class Autoencoder(nn.Module):
            def __init__(input_self, input_size, hidden_size):
                super().__init__()
                input_self.encoder = nn.Sequential(
                    nn.Linear(input_size, hidden_size),
                    nn.ReLU(),
                    nn.Linear(hidden_size, 2),
                )
                input_self.decoder = nn.Sequential(
                    nn.Linear(2, hidden_size),
                    nn.ReLU(),
                    nn.Linear(hidden_size, input_size),
                )

            def forward(input_self, values):
                return input_self.decoder(input_self.encoder(values))

        return torch, Autoencoder

    def train(self, normal_features: np.ndarray) -> "PyTorchAutoencoderDetector":
        torch, Autoencoder = self._torch_and_model()
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)

        x = np.asarray(normal_features, dtype=np.float32)
        if x.ndim != 2 or x.shape[0] < 20:
            raise ValueError("normal_features must be a 2-D array with at least 20 rows")
        if x.shape[1] != len(FEATURE_NAMES):
            raise ValueError(f"Expected {len(FEATURE_NAMES)} features, got {x.shape[1]}")
        if not np.all(np.isfinite(x)):
            raise ValueError("normal_features contain NaN or Inf")

        rng = np.random.default_rng(self.seed)
        indices = rng.permutation(len(x))
        split = max(1, int(round(0.8 * len(x))))
        train_idx, validation_idx = indices[:split], indices[split:]
        if len(validation_idx) == 0:
            validation_idx = indices[-1:]

        self.mean = np.mean(x[train_idx], axis=0).astype(np.float32)
        self.std = np.std(x[train_idx], axis=0).astype(np.float32)
        self.std = np.where(self.std > 1e-6, self.std, 1.0).astype(np.float32)
        train_z = ((x[train_idx] - self.mean) / self.std).astype(np.float32)
        validation_z = ((x[validation_idx] - self.mean) / self.std).astype(np.float32)

        self.model = Autoencoder(train_z.shape[1], self.hidden_size)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.learning_rate)
        criterion = torch.nn.MSELoss()
        train_tensor = torch.from_numpy(train_z)

        self.model.train()
        for _ in range(self.epochs):
            optimizer.zero_grad()
            reconstruction = self.model(train_tensor)
            loss = criterion(reconstruction, train_tensor)
            loss.backward()
            optimizer.step()

        self.model.eval()
        with torch.no_grad():
            validation_tensor = torch.from_numpy(validation_z)
            reconstruction = self.model(validation_tensor)
            scores = torch.mean(torch.square(validation_tensor - reconstruction), dim=1).numpy()
        self.threshold = float(np.percentile(scores, self.percentile))
        self.trained = True
        return self

    def save(self, directory: str) -> str:
        if not self.trained or self.model is None:
            raise RuntimeError("Cannot save an untrained PyTorch autoencoder")
        import torch
        os.makedirs(directory, exist_ok=True)
        model_path = os.path.join(directory, "pytorch_autoencoder.pt")
        metadata_path = os.path.join(directory, "pytorch_autoencoder.json")
        mean_tensor = __import__("torch").from_numpy(np.asarray(self.mean, dtype=np.float32))
        std_tensor = __import__("torch").from_numpy(np.asarray(self.std, dtype=np.float32))
        torch.save({
            "state_dict": self.model.state_dict(),
            "mean": mean_tensor,
            "std": std_tensor,
            "threshold": float(self.threshold),
            "feature_names": list(FEATURE_NAMES),
            "model_version": PYTORCH_MODEL_VERSION,
            "framework_version": str(torch.__version__),
            "hidden_size": int(self.hidden_size),
            "training_config": json.dumps({
                "seed": self.seed, "epochs": self.epochs,
                "percentile": self.percentile, "learning_rate": self.learning_rate,
                "normal_only": True, "train_fraction": 0.8,
            }),
        }, model_path)
        metadata = {
            "detector_type": self.kind,
            "model_version": PYTORCH_MODEL_VERSION,
            "framework": "torch",
            "framework_version": torch.__version__,
            "feature_names": list(FEATURE_NAMES),
            "threshold": float(self.threshold),
            "threshold_method": f"normal validation {self.percentile:.1f}th percentile",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "training": {"normal_only": True, "seed": self.seed, "epochs": self.epochs,
                         "train_fraction": 0.8, "percentile": self.percentile},
        }
        with open(metadata_path, "w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2)
        return model_path

    @classmethod
    def load(cls, directory: str) -> "PyTorchAutoencoderDetector":
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("PyTorch is not installed") from exc
        model_path = os.path.join(directory, "pytorch_autoencoder.pt")
        if not os.path.isfile(model_path):
            raise FileNotFoundError("Model is not trained: pytorch_autoencoder.pt was not found")
        try:
            try:
                payload = torch.load(model_path, map_location="cpu", weights_only=True)
            except TypeError:
                payload = torch.load(model_path, map_location="cpu")
            if payload["model_version"] != PYTORCH_MODEL_VERSION:
                raise ValueError("Incompatible model version")
            if tuple(payload["feature_names"]) != FEATURE_NAMES:
                raise ValueError("Incompatible feature metadata")
            obj = cls()
            obj.mean = payload["mean"].numpy()
            obj.std = payload["std"].numpy()
            obj.threshold = float(payload["threshold"])
            obj.hidden_size = int(payload["hidden_size"])
            _, Autoencoder = obj._torch_and_model()
            obj.model = Autoencoder(len(FEATURE_NAMES), obj.hidden_size)
            obj.model.load_state_dict(payload["state_dict"])
            obj.model.eval()
            obj.trained = True
            return obj
        except Exception as exc:
            raise ValueError(f"Corrupt or incompatible PyTorch model: {exc}") from exc

    def score(self, feature_vector: np.ndarray) -> float:
        if not self.trained or self.model is None:
            raise RuntimeError("PyTorch autoencoder is not trained")
        import torch
        x = np.asarray(feature_vector, dtype=np.float32)
        if x.shape != (len(FEATURE_NAMES),):
            raise ValueError(f"Incompatible feature vector: expected {len(FEATURE_NAMES)} values")
        if not np.all(np.isfinite(x)):
            raise ValueError("Feature vector contains NaN or Inf")
        z = ((x - self.mean) / self.std).astype(np.float32)
        tensor = torch.from_numpy(z.reshape(1, -1))
        with torch.no_grad():
            reconstruction = self.model(tensor)
            score = torch.mean(torch.square(tensor - reconstruction), dim=1).item()
        return float(score)

    def predict(self, feature_vector: np.ndarray, source_id: str = "SYNTHETIC",
                timestamp: Optional[str] = None, signal_type: str = "ACOUSTIC",
                input_mode: str = "synthetic") -> dict:
        score = self.score(feature_vector)
        status = "ANOMALY" if score >= self.threshold else "NORMAL"
        summary = {name: float(value) for name, value in zip(FEATURE_NAMES, np.asarray(feature_vector))}
        return {
            "source_id": source_id,
            "timestamp": timestamp,
            "signal_type": signal_type,
            "anomaly_score": score,
            "threshold": float(self.threshold),
            "status": status,
            "model_version": PYTORCH_MODEL_VERSION,
            "feature_summary": summary,
            "input_mode": input_mode,
            "detector_type": self.kind,
        }
