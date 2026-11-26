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
    source_type: Optional[str] = None


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
            if self._sdr is not None:
                try:
                    self._sdr.close()
                except Exception:
                    pass
                self._sdr = None
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
                    source_type="LIVE_HARDWARE",
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
            t = np.arange(chunk_size) / sr
            window_number = self._window_counter
            drift_hz = 80_000.0 + 40_000.0 * np.sin(window_number * 0.08)
            changing_carrier = 0.08 * np.exp(1j * 2 * np.pi * drift_hz * t)
            samples = samples + changing_carrier.astype(np.complex64)

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
                source_type="SYNTHETIC_SIMULATION",
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

    def save_window_with_metadata(
        self,
        window: IQSampleWindow,
        output_npy_path: str,
        metadata_json_path: Optional[str] = None,
        sensor_id: str = "SDR-01",
    ) -> dict:
        """
        Save an IQSampleWindow to .npy and write complete Day 1 RF provenance metadata JSON.
        """
        import os
        from aetherhound.core.evidence_metadata import (
            SOURCE_TYPE_LIVE_HARDWARE,
            SOURCE_TYPE_RECORDED_HARDWARE,
            SOURCE_TYPE_SYNTHETIC_SIMULATION,
            SOURCE_TYPE_VIRTUAL_SDR,
            SOURCE_TYPE_VIRTUAL_SDR,
            build_rf_metadata,
            compute_array_sha256,
            save_metadata,
        )

        os.makedirs(os.path.dirname(os.path.abspath(output_npy_path)), exist_ok=True)
        np.save(output_npy_path, window.samples)
        raw_hash = compute_array_sha256(window.samples)

        source_type = window.source_type
        if source_type is None and window.is_synthetic:
            source_type = SOURCE_TYPE_SYNTHETIC_SIMULATION
        if source_type not in (
            SOURCE_TYPE_LIVE_HARDWARE,
            SOURCE_TYPE_RECORDED_HARDWARE,
            SOURCE_TYPE_SYNTHETIC_SIMULATION,
        ):
            raise ValueError("IQ window requires explicit source provenance before saving")
        is_syn = source_type == SOURCE_TYPE_SYNTHETIC_SIMULATION
        if bool(window.is_synthetic) != is_syn:
            raise ValueError("IQ window synthetic flag conflicts with its source provenance")
        acq_mode = (
            "Synthetic Complex IQ Simulation"
            if is_syn
            else "Recorded Hardware IQ Data"
            if source_type == SOURCE_TYPE_RECORDED_HARDWARE
            else "RTL-SDR Hardware IQ Stream"
        )
        meta_path = metadata_json_path or (os.path.splitext(output_npy_path)[0] + ".json")

        meta = build_rf_metadata(
            sensor_id=f"{sensor_id} (SYNTHETIC IQ BUFFER)" if is_syn else sensor_id,
            source_type=source_type,
            center_freq_hz=window.center_freq_hz,
            sample_rate_hz=window.sample_rate_hz,
            rf_gain=self.config.gain,
            sample_count=len(window.samples),
            fft_size=self.config.fft_size,
            data_file=output_npy_path,
            acquisition_mode=acq_mode,
            data_sha256=raw_hash,
            timestamp_epoch=window.timestamp,
        )
        meta["capture_status"] = "COMPLETED"
        meta["device_identifier"] = sensor_id
        save_metadata(meta, meta_path)
        return meta


def capture_recording(
    config: Optional[RFConfig] = None,
    duration_sec: float = 1.0,
    output_dir: str = "data/rf/raw",
    device: Optional[RFCaptureDevice] = None,
) -> dict:
    """Capture a bounded RF recording, spectrum, and integrity metadata."""
    import os

    from aetherhound.core.evidence_metadata import (
        SOURCE_TYPE_LIVE_HARDWARE,
        build_rf_metadata,
        compute_file_sha256,
        generate_capture_id,
        save_metadata,
    )
    from aetherhound.dsp.fft_engine import compute_power_spectrum_db

    if duration_sec <= 0:
        raise ValueError("Capture duration must be greater than zero")
    cfg = config or RFConfig()
    cfg.validate()
    capture_device = device or RFCaptureDevice(cfg)
    if capture_device.synthetic_mode:
        raise ValueError("RF hardware recording requires a physical RTL-SDR device")
    if not capture_device.start():
        raise RuntimeError(getattr(capture_device, "_last_error", None) or "RTL-SDR device unavailable")

    windows = []
    deadline = time.monotonic() + duration_sec
    try:
        while time.monotonic() < deadline:
            window = capture_device.get_window(timeout=min(0.2, max(0.01, deadline - time.monotonic())))
            if window is not None:
                windows.append(window)
    finally:
        capture_device.stop()

    if not windows:
        raise RuntimeError("RTL-SDR started but returned no IQ samples")

    iq_samples = np.concatenate([window.samples for window in windows]).astype(np.complex64, copy=False)
    timestamp = windows[0].timestamp
    capture_id = generate_capture_id("RF")
    os.makedirs(output_dir, exist_ok=True)
    raw_path = os.path.abspath(os.path.join(output_dir, f"{capture_id}.npy"))
    spectrum_path = os.path.abspath(os.path.join(output_dir, f"{capture_id}.spectrum.npz"))
    metadata_path = os.path.abspath(os.path.join(output_dir, f"{capture_id}.json"))
    np.save(raw_path, iq_samples)

    frequencies_hz, spectrum_db = compute_power_spectrum_db(
        iq_samples,
        fft_size=cfg.fft_size,
        sample_rate_hz=cfg.sample_rate_hz,
        center_freq_hz=cfg.center_freq_hz,
    )
    np.savez_compressed(spectrum_path, frequencies_hz=frequencies_hz, power_db=spectrum_db)
    peak_index = int(np.argmax(spectrum_db))
    try:
        device_identifier = str(capture_device._sdr.get_device_name(cfg.device_index))
    except Exception:
        device_identifier = f"RTL-SDR device index {cfg.device_index}"

    metadata = build_rf_metadata(
        sensor_id=device_identifier,
        source_type=SOURCE_TYPE_LIVE_HARDWARE,
        center_freq_hz=cfg.center_freq_hz,
        sample_rate_hz=cfg.sample_rate_hz,
        rf_gain=cfg.gain,
        sample_count=len(iq_samples),
        fft_size=cfg.fft_size,
        data_file=raw_path,
        acquisition_mode="RTL-SDR Hardware IQ Capture",
        data_sha256=compute_file_sha256(raw_path),
        capture_id=capture_id,
        timestamp_epoch=timestamp,
        noise_floor_db=float(np.median(spectrum_db)),
        peak_freq_hz=float(frequencies_hz[peak_index]),
        peak_power_db=float(spectrum_db[peak_index]),
    )
    metadata.update(
        {
            "device_identifier": device_identifier,
            "capture_status": "COMPLETED",
            "spectrum_file": spectrum_path,
            "spectrum_sha256": compute_file_sha256(spectrum_path),
        }
    )
    save_metadata(metadata, metadata_path)
    return {
        "capture_id": capture_id,
        "capture_status": "COMPLETED",
        "raw_iq_file": raw_path,
        "spectrum_file": spectrum_path,
        "metadata_file": metadata_path,
        "sample_count": len(iq_samples),
        "metadata": metadata,
    }


def main() -> None:
    import argparse
    from aetherhound.hardware.device_check import check_rtlsdr

    parser = argparse.ArgumentParser(description="Acquire RTL-SDR IQ captures")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="Check for connected RTL-SDR devices")
    capture_parser = subparsers.add_parser("capture", help="Capture IQ samples and an RF spectrum")
    capture_parser.add_argument("--duration", type=float, default=1.0, help="Capture duration in seconds")
    capture_parser.add_argument("--output-dir", default="data/rf/raw")
    args = parser.parse_args()

    if args.command == "list":
        result = check_rtlsdr()
        print(f"{'CONNECTED' if result.connected else 'DISCONNECTED'}: {result.name}")
        if result.error_message:
            print(f"Details: {result.error_message}")
        return
    try:
        result = capture_recording(duration_sec=args.duration, output_dir=args.output_dir)
    except (RuntimeError, ValueError, OSError) as exc:
        parser.exit(1, f"RF capture failed: {exc}\n")
    print(f"Capture {result['capture_id']} {result['capture_status']}: {result['sample_count']} samples")
    print(f"IQ: {result['raw_iq_file']}\nSpectrum: {result['spectrum_file']}\nMetadata: {result['metadata_file']}")


if __name__ == "__main__":
    main()


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
        source_type="SYNTHETIC_SIMULATION",
    )
