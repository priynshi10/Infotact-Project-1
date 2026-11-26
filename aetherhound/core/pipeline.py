"""Software-only end-to-end synthetic/file signal pipeline contract."""

from datetime import datetime, timezone
from typing import Literal, Optional

import numpy as np

from aetherhound.detection.anomaly_detector import (
    NumPyAnomalyDetector,
    PyTorchAutoencoderDetector,
    extract_numeric_features,
)
from aetherhound.core.event_store import append_event


class SignalPipelineResult(dict):
    pass


def run_pipeline(
    samples: np.ndarray,
    sample_rate_hz: float,
    detector,
    source_id: str,
    signal_type: Literal["RF", "ACOUSTIC"],
    input_mode: Literal["synthetic", "file", "hardware"],
) -> dict:
    if input_mode not in ("synthetic", "file", "hardware"):
        raise ValueError("input_mode must be synthetic, file or hardware")
    if input_mode == "hardware" and np.asarray(samples).size == 0:
        raise RuntimeError("Hardware input returned no samples")
    features = extract_numeric_features(samples, sample_rate_hz)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = detector.predict(
        features,
        source_id=source_id,
        timestamp=timestamp,
        signal_type=signal_type,
        input_mode=input_mode,
    )
    append_event(result)
    return result
