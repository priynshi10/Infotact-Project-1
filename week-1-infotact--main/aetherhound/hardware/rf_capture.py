"""
AetherHound RF Acquisition Module
Continuous real-time acquisition of IQ samples via RTL-SDR
using non-blocking asynchronous callbacks and thread-safe bounded queues.
Also supports synthetic IQ generation for hardware-independent test modes.
"""

from dataclasses import dataclass
import queue
import threading
import time
from typing import Callable, Optional, Tuple, Union

import numpy as np

from aetherhound.hardware.config import RFConfig, RTL_STABLE_SAMPLE_RATE


@dataclass
class IQSampleWindow:
    """A timestamped window of complex IQ samples."""
    samples: np.ndarray          # Complex64 or complex128 array
    timestamp: float             # POSIX epoch timestamp
    center_freq_hz: float
    sample_rate_hz: float
    is_synthetic: bool = False
    window_id: int = 0
    dropped_before: int = 0


class RFCaptureDevice:
    """
    RTL-SDR acquisition controller.
    Runs continuous sample streaming without blocking the acquisition thread.
    """

    def __init__(
        self,
        config: Optional[RFConfig] = None,
        queue_size: int = 64,
        synthetic_mode: bool = False,
    ):
        self.config = config or RFConfig()
        self.config.validate()
        self.synthetic_mode = synthetic_mode

        self._queue: "queue.Queue[IQSampleWindow]" = queue.Queue(maxsize=queue_size)
        self._is_running = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._sdr = None

        self._dropped_windows = 0
        self._window_counter = 0
        self._total_samples_acquired = 0
        self._start_time: Optional[float] = None
        self._last_error: Optional[str] = None
        self._connected = False

    @property
    def is_running(self) -> bool:
        return self._is_running.is_set()

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def queue(self) -> "queue.Queue[IQSampleWindow]":
        return self._queue

    @property
    def dropped_count(self) -> int:
        return self._dropped_windows

    @property
    def total_samples(self) -> int:
        return self._total_samples_acquired

    def start(self) -> bool:
        """Start continuous RF acquisition."""
        if self._is_running.is_set():
            return True

        if not self.synthetic_mode:
            success = self._init_hardware()
            if not success:
                return False
        else:
            self._connected = True

        self._is_running.set()
        self._start_time = time.time()

        if self.synthetic_mode:
            self._thread = threading.Thread(
                target=self._synthetic_acquisition_loop,
                name="AetherHound-RFSyntheticWorker",
                daemon=True,
            )
        else:
            self._thread = threading.Thread(
                target=self._hardware_acquisition_loop,
                name="AetherHound-RFHardwareWorker",
                daemon=True,
            )

        self._thread.start()
        return True

    def stop(self) -> None:
        """Stop acquisition and perform safe hardware cleanup."""
        self._is_running.clear()

        # Signal hardware SDR to cancel async reads
        if self._sdr is not None:
            try:
                # pyrtlsdr cancel_read_async
                if hasattr(self._sdr, "cancel_read_async"):
                    self._sdr.cancel_read_async()
            except Exception:
                pass

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.5)

        if self._sdr is not None:
            try:
                self._sdr.close()
            except Exception:
                pass
            self._sdr = None

        self._connected = False

    def get_window(self, timeout: float = 0.5) -> Optional[IQSampleWindow]:
        """Fetch the next IQ sample window from the queue."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _init_hardware(self) -> bool:
        """Initialize the RTL-SDR physical dongle."""
        try:
            import rtlsdr
            self._sdr = rtlsdr.RtlSdr(self.config.device_index)
            self._sdr.sample_rate = float(self.config.sample_rate_hz)
            self._sdr.center_freq = float(self.config.center_freq_hz)

            if isinstance(self.config.gain, str) and self.config.gain.lower() == "auto":
                self._sdr.gain = "auto"
            else:
                self._sdr.gain = float(self.config.gain)

            if self.config.ppm_correction != 0:
                self._sdr.freq_correction = self.config.ppm_correction

            self._connected = True
            self._last_error = None
            return True
        except Exception as e:
            self._connected = False
            self._last_error = f"RTL-SDR initialization failure: {str(e)}"
            return False

    def _hardware_acquisition_loop(self) -> None:
        """Continuous hardware acquisition loop using read_samples."""
        chunk_size = self.config.samples_per_window
        while self._is_running.is_set():
            try:
                # read_samples returns complex numpy array
                samples = self._sdr.read_samples(chunk_size)
                now = time.time()
                self._window_counter += 1
                self._total_samples_acquired += len(samples)

                window = IQSampleWindow(
                    samples=samples,
                    timestamp=now,
                    center_freq_hz=self.config.center_freq_hz,
                    sample_rate_hz=self.config.sample_rate_hz,
                    is_synthetic=False,
                    window_id=self._window_counter,
                    dropped_before=self._dropped_windows,
                )

                try:
                    self._queue.put_nowait(window)
                except queue.Full:
                    # Bounded queue full: drop oldest to keep live real-time latency minimal
                    try:
                        self._queue.get_nowait()
                        self._queue.put_nowait(window)
                    except Exception:
                        pass
                    self._dropped_windows += 1

            except Exception as ex:
                self._last_error = f"Hardware read error: {ex}"
                self._connected = False
                break

    def inject_test_burst(
        self,
        carrier_offset_hz: float = 150_000.0,
        num_windows: int = 5,
        amplitude: float = 0.70,
    ) -> None:
        """Inject a narrowband RF carrier burst into the synthetic acquisition stream."""
        self._inject_offset_hz = carrier_offset_hz
        self._inject_remaining_windows = num_windows
        self._inject_amplitude = amplitude

    def _synthetic_acquisition_loop(self) -> None:
        """
        Synthetic RF IQ sample generator for testing without physical SDR.
        Generates Gaussian thermal noise floor with realistic SNR and
        optional test bursts.
        """
        chunk_size = self.config.samples_per_window
        sr = self.config.sample_rate_hz
        duration_per_chunk = chunk_size / sr

        # Thermal noise floor around -100 dBm / unit variance
        rng = np.random.default_rng(seed=42)
        self._inject_remaining_windows = getattr(self, "_inject_remaining_windows", 0)
        self._inject_offset_hz = getattr(self, "_inject_offset_hz", 0.0)
        self._inject_amplitude = getattr(self, "_inject_amplitude", 0.0)

        while self._is_running.is_set():
            loop_start = time.time()

            # Base thermal complex Gaussian noise
            i_noise = rng.normal(0, 0.04, chunk_size)
            q_noise = rng.normal(0, 0.04, chunk_size)
            samples = (i_noise + 1j * q_noise).astype(np.complex64)

            # Check if test carrier burst active
            if self._inject_remaining_windows > 0:
                t = np.arange(chunk_size) / sr
                carrier = self._inject_amplitude * np.exp(1j * 2 * np.pi * self._inject_offset_hz * t)
                samples = samples + carrier.astype(np.complex64)
                self._inject_remaining_windows -= 1

            now = time.time()
            self._window_counter += 1
            self._total_samples_acquired += chunk_size

            window = IQSampleWindow(
                samples=samples.astype(np.complex64),
                timestamp=now,
                center_freq_hz=self.config.center_freq_hz,
                sample_rate_hz=self.config.sample_rate_hz,
                is_synthetic=True,
                window_id=self._window_counter,
                dropped_before=self._dropped_windows,
            )

            try:
                self._queue.put_nowait(window)
            except queue.Full:
                try:
                    self._queue.get_nowait()
                    self._queue.put_nowait(window)
                except Exception:
                    pass
                self._dropped_windows += 1

            # Regulate pacing to match real sample rate
            elapsed = time.time() - loop_start
            sleep_time = max(0.001, duration_per_chunk - elapsed)
            time.sleep(sleep_time)


def inject_synthetic_rf_carrier(
    window: IQSampleWindow,
    carrier_offset_hz: float,
    snr_db: float = 20.0,
    amplitude: float = 0.5,
) -> IQSampleWindow:
    """
    Utility for testing: injects a narrowband continuous carrier into an IQ window.
    """
    n = len(window.samples)
    t = np.arange(n) / window.sample_rate_hz
    carrier = amplitude * np.exp(1j * 2 * np.pi * carrier_offset_hz * t)
    mod_samples = window.samples + carrier.astype(np.complex64)
    return IQSampleWindow(
        samples=mod_samples,
        timestamp=window.timestamp,
        center_freq_hz=window.center_freq_hz,
        sample_rate_hz=window.sample_rate_hz,
        is_synthetic=True,
        window_id=window.window_id,
        dropped_before=window.dropped_before,
    )
