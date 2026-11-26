# ML Anomaly Detection

## Working baseline

The default detector is `NumPyAnomalyDetector`, a Mahalanobis-distance baseline over standardized numeric features. It is not a neural network. It is intentionally offline and CPU-friendly.

PyTorch was detected during the environment audit. The project can expose an optional autoencoder model definition, but the saved CLI baseline uses NumPy until a trained neural model is implemented and verified.

## Features

RMS, peak amplitude, crest factor, dominant frequency, spectral centroid, spectral bandwidth, and spectral flatness are extracted in `aetherhound/detection/anomaly_detector.py`.

## Dataset

`generate_synthetic_dataset()` creates deterministic normal tones/noise and controlled periodic anomalies. Normal fixtures establish training and validation statistics. Test anomalies are never used to choose the threshold.

## Training and threshold

The normal-only split is standardized and covariance-distanced. The default threshold is the 95th percentile of normal validation reconstruction-like scores. Seed and percentile are explicit CLI inputs.

## Commands

```powershell
python -m aetherhound.scripts.ml_demo generate-data
python -m aetherhound.scripts.ml_demo train --count 200 --seed 2026 --percentile 95 --model-dir data/models/anomaly
python -m aetherhound.scripts.ml_demo score --model-dir data/models/anomaly --seed 2026
python -m aetherhound.scripts.ml_demo train --detector pytorch_autoencoder --count 200 --epochs 30 --model-dir data/models/anomaly
python -m aetherhound.scripts.ml_demo score --detector pytorch_autoencoder --model-dir data/models/anomaly
python -m aetherhound.scripts.ml_demo evaluate --detector pytorch_autoencoder --model-dir data/models/anomaly --count 50 --seed 9090
python -m aetherhound.scripts.ml_demo status --model-dir data/models/anomaly --seed 2026
```

No measured real-world accuracy is claimed. The score and status are demonstrations over synthetic fixtures only.
