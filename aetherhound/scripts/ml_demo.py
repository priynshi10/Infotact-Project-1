"""Train and score the synthetic offline anomaly detector."""

import argparse
import os
from datetime import datetime, timezone

import numpy as np

from aetherhound.core.event_store import append_event
from aetherhound.detection.anomaly_detector import (
    generate_synthetic_dataset,
    NumPyAnomalyDetector,
    train_numpy_baseline,
    PyTorchAutoencoderDetector,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="AetherHound synthetic ML anomaly demo")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("generate-data", help="Generate controlled synthetic normal/anomaly fixtures")
    train = subparsers.add_parser("train", help="Train normal-only NumPy baseline")
    train.add_argument("--count", type=int, default=200)
    train.add_argument("--seed", type=int, default=2026)
    train.add_argument("--percentile", type=float, default=95.0)
    train.add_argument("--model-dir", default="data/models/anomaly")
    train.add_argument("--detector", choices=("numpy_baseline", "pytorch_autoencoder"), default="numpy_baseline")
    train.add_argument("--epochs", type=int, default=30)
    score = subparsers.add_parser("score", help="Score a generated synthetic signal")
    score.add_argument("--model-dir", default="data/models/anomaly")
    score.add_argument("--seed", type=int, default=2026)
    score.add_argument("--event-file", default="ml_anomaly_events.jsonl")
    score.add_argument("--detector", choices=("numpy_baseline", "pytorch_autoencoder"), default="numpy_baseline")
    evaluate = subparsers.add_parser("evaluate", help="Evaluate a held-out labelled synthetic fixture set")
    evaluate.add_argument("--detector", choices=("numpy_baseline", "pytorch_autoencoder"), default="numpy_baseline")
    evaluate.add_argument("--model-dir", default="data/models/anomaly")
    evaluate.add_argument("--count", type=int, default=50)
    evaluate.add_argument("--seed", type=int, default=9090)
    status = subparsers.add_parser("status", help="Show detector availability and model state")
    status.add_argument("--model-dir", default="data/models/anomaly")
    args = parser.parse_args()

    if args.command == "generate-data":
        x, y = generate_synthetic_dataset()
        print(f"Generated {len(x)} synthetic feature rows: "
              f"{int(np.sum(y == 0))} normal, {int(np.sum(y == 1))} anomaly")
        return

    if args.command == "train":
        x, y = generate_synthetic_dataset(count_per_class=args.count, seed=args.seed)
        normal = x[y == 0]
        if args.detector == "numpy_baseline":
            detector, summary = train_numpy_baseline(normal, args.model_dir, args.percentile)
            print(f"Trained {summary['detector_type']} on {summary['normal_sample_count']} normal fixtures")
            print(f"Threshold ({summary['threshold_method']}): {summary['threshold']:.6f}")
            print(f"Model: {summary['model_path']}")
        else:
            try:
                detector = PyTorchAutoencoderDetector(
                    percentile=args.percentile, seed=args.seed, epochs=args.epochs,
                ).train(normal)
            except RuntimeError as exc:
                parser.exit(1, f"{exc}\n")
            model_path = detector.save(args.model_dir)
            print(f"Trained pytorch_autoencoder on {len(normal)} normal synthetic fixtures")
            print(f"Threshold (normal validation {args.percentile:.1f}th percentile): {detector.threshold:.6f}")
            print(f"Model: {os.path.abspath(model_path)}")
        return

    if args.command == "score":
        try:
            if args.detector == "numpy_baseline":
                detector = NumPyAnomalyDetector.load(args.model_dir)
            else:
                detector = PyTorchAutoencoderDetector.load(args.model_dir)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.exit(1, f"{exc}\n")
        x, y = generate_synthetic_dataset(count_per_class=20, seed=args.seed)
        normal_feature = x[y == 0][0]
        anomaly_feature = x[y == 1][0]
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        normal = detector.predict(normal_feature, "SYNTHETIC-MIC-01", timestamp, "ACOUSTIC", "synthetic")
        anomaly = detector.predict(anomaly_feature, "SYNTHETIC-MIC-01", timestamp, "ACOUSTIC", "synthetic")
        append_event(normal, filename=args.event_file)
        append_event(anomaly, filename=args.event_file)
        print(f"{args.detector} synthetic normal prediction:", normal["status"],
              f"score={normal['anomaly_score']:.6f}", f"threshold={normal['threshold']:.6f}")
        print(f"{args.detector} synthetic anomaly prediction:", anomaly["status"],
              f"score={anomaly['anomaly_score']:.6f}", f"threshold={anomaly['threshold']:.6f}")
        return

    if args.command == "evaluate":
        try:
            detector = (NumPyAnomalyDetector.load(args.model_dir)
                        if args.detector == "numpy_baseline"
                        else PyTorchAutoencoderDetector.load(args.model_dir))
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            parser.exit(1, f"{exc}\n")
        x, y = generate_synthetic_dataset(count_per_class=args.count, seed=args.seed)
        predictions = np.array([detector.predict(row)["status"] == "ANOMALY" for row in x])
        labels = y.astype(bool)
        tp = int(np.sum(predictions & labels))
        tn = int(np.sum(~predictions & ~labels))
        fp = int(np.sum(predictions & ~labels))
        fn = int(np.sum(~predictions & labels))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        accuracy = (tp + tn) / len(labels)
        print(f"{args.detector} held-out synthetic evaluation")
        print(f"Accuracy={accuracy:.3f} Precision={precision:.3f} Recall={recall:.3f}")
        print(f"Confusion matrix: TN={tn} FP={fp} FN={fn} TP={tp}")
        return

    import importlib.util
    torch_available = importlib.util.find_spec("torch") is not None
    numpy_model = os.path.isfile(os.path.join(args.model_dir, "anomaly_model.npz"))
    pytorch_model = os.path.isfile(os.path.join(args.model_dir, "pytorch_autoencoder.pt"))
    print("numpy_baseline: AVAILABLE; model=" + ("TRAINED" if numpy_model else "NOT TRAINED"))
    print("pytorch_autoencoder:", "AVAILABLE" if torch_available else "UNAVAILABLE",
          "; model=" + ("TRAINED" if pytorch_model else "NOT TRAINED"))


if __name__ == "__main__":
    main()
