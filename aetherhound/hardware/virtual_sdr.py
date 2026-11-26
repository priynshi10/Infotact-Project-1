"""Virtual receive-only SDR with generated and file-based complex IQ sources."""

from dataclasses import dataclass
import os
import queue
import threading
import time
from typing import Iterable, Optional

import numpy as np

from aetherhound.hardware.rf_capture import IQSampleWindow


SOURCE_TYPE_VIRTUAL_SDR = "VIRTUAL_SDR"


@dataclass
class VirtualSDRConfig:
    sample_rate_hz: float = 2_048_000.0
    center_freq_hz: float = 433_920_000.0
    bandwidth_hz: float = 1_024_000.0
    amplitude: float = 0.5
    noise_amplitude: float = 0.02
    chunk_size: int = 16384
    seed: int = 2026

    def __post_init__(self) -> None:
        self.bandwidth_hz = min(
            float(self.bandwidth_hz),
            float(self.sample_rate_hz),
        )

    def validate(self) -> None:
        if not np.isfinite(self.sample_rate_hz) or self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        if not np.isfinite(self.center_freq_hz) or self.center_freq_hz < 0:
            raise ValueError("center_freq_hz must be non-negative")
        if not np.isfinite(self.bandwidth_hz) or not 0 < self.bandwidth_hz <= self.sample_rate_hz:
            raise ValueError("bandwidth_hz must be positive and fit the sample rate")
        if not np.isfinite(self.amplitude) or self.amplitude < 0:
            raise ValueError("amplitude must be non-negative")
        if not np.isfinite(self.noise_amplitude) or self.noise_amplitude < 0:
            raise ValueError("noise_amplitude must be non-negative")
        if self.chunk_size < 2:
            raise ValueError("chunk_size must be at least 2")


class VirtualSDR:
    """Threaded, bounded virtual receiver; never emits or performs transmission."""

    def __init__(
        self,
        config: Optional[VirtualSDRConfig] = None,
        components_hz: Optional[Iterable[float]] = None,
        queue_size: int = 64,
        loop_file: bool = False,
    ):
        self.config = config or VirtualSDRConfig()
        self.config.validate()
        self.components_hz = tuple(float(v) for v in (components_hz or (150_000.0,)))
        self.loop_file = bool(loop_file)
        self.queue: "queue.Queue[IQSampleWindow]" = queue.Queue(maxsize=queue_size)
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._window_counter = 0
        self._dropped = 0
        self._file_samples: Optional[np.ndarray] = None
        self._last_error: Optional[str] = None

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    @property
    def dropped_count(self) -> int:
        return self._dropped

    def generate_block(self, offset_samples: int = 0) -> np.ndarray:
        """Generate one deterministic complex-IQ block."""
        count = self.config.chunk_size
        rng = np.random.default_rng(self.config.seed)
        t = (np.arange(count, dtype=np.float64) + offset_samples) / self.config.sample_rate_hz
        samples = self.config.noise_amplitude * (
            rng.normal(size=count) + 1j * rng.normal(size=count)
        )
        for component_hz in self.components_hz:
            if abs(component_hz) > 0.5 * self.config.sample_rate_hz:
                raise ValueError("component frequency exceeds Nyquist limit")
            samples = samples + self.config.amplitude * np.exp(
                2j * np.pi * component_hz * t
            )
        result = np.asarray(samples, dtype=np.complex64)
        if not np.all(np.isfinite(result)):
            raise ValueError("Virtual SDR generated non-finite IQ samples")
        return result

    def load_iq_file(self, path: str) -> np.ndarray:
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        if path.lower().endswith(".npy"):
            samples = np.load(path, allow_pickle=False)
        elif path.lower().endswith(".npz"):
            with np.load(path, allow_pickle=False) as archive:
                if "iq" not in archive:
                    raise ValueError("NPZ IQ file must contain an 'iq' array")
                samples = archive["iq"]
        else:
            raise ValueError("Supported IQ file formats are .npy and .npz")
        samples = np.asarray(samples)
        if samples.ndim != 1 or not np.iscomplexobj(samples):
            raise ValueError("IQ file must contain a one-dimensional complex array")
        if samples.size == 0:
            raise ValueError("IQ file contains no samples")
        if not np.all(np.isfinite(samples)):
            raise ValueError("IQ file contains NaN or Inf")
        self._file_samples = samples.astype(np.complex64, copy=False)
        return self._file_samples.copy()

    def start(self) -> bool:
        if self._running.is_set():
            return True
        self._running.set()
        self._thread = threading.Thread(
            target=self._stream_loop,
            name="AetherHound-VirtualSDR",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running.clear()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None

    def get_window(self, timeout: float = 0.5) -> Optional[IQSampleWindow]:
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def read_window(self) -> IQSampleWindow:
        self._window_counter += 1
        if self._file_samples is not None:
            start = ((self._window_counter - 1) * self.config.chunk_size)
            if start >= len(self._file_samples):
                if not self.loop_file:
                    raise EOFError("Virtual SDR IQ file playback reached end of file")
                start %= len(self._file_samples)
            block = self._file_samples[start:start + self.config.chunk_size]
            if len(block) < self.config.chunk_size:
                block = np.resize(block, self.config.chunk_size)
        else:
            block = self.generate_block(
                offset_samples=(self._window_counter - 1) * self.config.chunk_size
            )
        return IQSampleWindow(
            samples=block,
            timestamp=time.time(),
            center_freq_hz=self.config.center_freq_hz,
            sample_rate_hz=self.config.sample_rate_hz,
            is_synthetic=True,
            window_id=self._window_counter,
            dropped_before=self._dropped,
            source_type=SOURCE_TYPE_VIRTUAL_SDR,
        )

    def _stream_loop(self) -> None:
        pace = max(0.001, self.config.chunk_size / self.config.sample_rate_hz)
        while self._running.is_set():
            started = time.monotonic()
            try:
                window = self.read_window()
            except EOFError:
                self._running.clear()
                self._last_error = "IQ file playback complete"
                break
            except Exception as exc:
                self._running.clear()
                self._last_error = str(exc)
                break
            try:
                self.queue.put_nowait(window)
            except queue.Full:
                try:
                    self.queue.get_nowait()
                    self.queue.put_nowait(window)
                except Exception:
                    pass
                self._dropped += 1
            elapsed = time.monotonic() - started
            time.sleep(max(0.001, pace - elapsed))
