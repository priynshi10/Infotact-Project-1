"""Run a Virtual SDR through the existing DSP and optional detector pipeline."""

import argparse
import os
import time

from aetherhound.hardware.virtual_sdr import VirtualSDR, VirtualSDRConfig
from aetherhound.dsp.rf_processor import RFProcessor
from aetherhound.core.event_store import append_event
from aetherhound.detection.anomaly_detector import NumPyAnomalyDetector, extract_numeric_features


def main() -> None:
    parser = argparse.ArgumentParser(description="AetherHound Virtual SDR receiver")
    parser.add_argument("--backend", choices=("python", "gnuradio", "auto"), default="python")
    parser.add_argument("--seconds", type=float, default=2.0)
    parser.add_argument("--input-npy")
    parser.add_argument("--model-dir", default="data/models/anomaly")
    parser.add_argument("--sample-rate", type=float, default=2_048_000.0)
    parser.add_argument("--center-frequency", type=float, default=433_920_000.0)
    parser.add_argument("--component", type=float, action="append", default=[150_000.0])
    args = parser.parse_args()

    config = VirtualSDRConfig(
        sample_rate_hz=args.sample_rate,
        center_freq_hz=args.center_frequency,
        bandwidth_hz=min(args.sample_rate / 2.0, args.sample_rate),
    )
    receiver = VirtualSDR(config, components_hz=args.component)
    if args.input_npy:
        receiver.load_iq_file(args.input_npy)
    receiver.start()

    detector = None
    try:
        detector = NumPyAnomalyDetector.load(args.model_dir)
    except (FileNotFoundError, ValueError):
        detector = None

    processor = RFProcessor()
    deadline = time.monotonic() + max(0.2, args.seconds)
    last_result = None
    while time.monotonic() < deadline:
        window = receiver.get_window(timeout=0.2)
        if window is None:
            continue
        processed = processor.process_window(window)
        prediction = None
        if detector is not None:
            features = extract_numeric_features(window.samples, window.sample_rate_hz)
            prediction = detector.predict(
                features,
                source_id="VIRTUAL-SDR-01",
                signal_type="RF",
                input_mode="synthetic",
            )
            append_event(prediction)
        last_result = {
            "source": window.source_type,
            "backend": args.backend,
            "peak_hz": processed.max_peak_freq_hz,
            "ml_status": prediction["status"] if prediction else "NOT TRAINED",
        }
    receiver.stop()
    print("source:", last_result["source"] if last_result else "VIRTUAL_SDR")
    print("backend:", args.backend)
    print("peak_hz:", last_result["peak_hz"] if last_result else "none")
    print("ml_status:", last_result["ml_status"] if last_result else "NOT TRAINED")


if __name__ == "__main__":
    main()
