"""
AetherHound Real-Time Core Engine
Coordinates concurrent RF and Acoustic hardware acquisition, independent DSP pipelines,
continuous anomaly detection, Morse pattern recognition, performance metrics,
and non-blocking JSONL event logging.
"""

from dataclasses import asdict, dataclass, field
import json
import os
import queue
import threading
import time
from typing import Callable, Deque, Dict, List, Optional
from collections import deque

import numpy as np

from aetherhound.detection.acoustic_detector import AcousticAlertEvent, AcousticDetector
from aetherhound.detection.morse_detector import MorsePatternEvent, RealtimeMorseDetector
from aetherhound.detection.rf_detector import RFAlertEvent, RFDetector
from aetherhound.dsp.acoustic_processor import AcousticProcessedChunk, AcousticProcessor
from aetherhound.dsp.rf_processor import RFProcessedWindow, RFProcessor
from aetherhound.hardware.acoustic_capture import AcousticCaptureDevice
from aetherhound.hardware.config import HardwareConfig
from aetherhound.hardware.rf_capture import RFCaptureDevice


@dataclass
class EngineTelemetry:
    """Real-time performance and pipeline metrics."""
    uptime_sec: float = 0.0
    rf_connected: bool = False
    mic_connected: bool = False
    is_paused: bool = False

    # RF Metrics
    rf_center_freq_hz: float = 0.0
    rf_sample_rate_hz: float = 0.0
    rf_queue_fill: int = 0
    rf_dropped_windows: int = 0
    rf_processing_latency_ms: float = 0.0
    rf_windows_processed: int = 0
    rf_noise_floor_db: float = 0.0
    rf_peak_power_db: float = 0.0
    rf_peak_freq_hz: float = 0.0
    rf_status: str = "NORMAL"

    # Acoustic Metrics
    acoustic_sample_rate_hz: int = 0
    acoustic_queue_fill: int = 0
    acoustic_dropped_chunks: int = 0
    acoustic_processing_latency_ms: float = 0.0
    acoustic_chunks_processed: int = 0
    acoustic_rms_energy: float = 0.0
    acoustic_dominant_freq_hz: float = 0.0
    acoustic_detected_pulses: int = 0
    acoustic_status: str = "NORMAL"
    morse_status: str = "NO PATTERN"

    # Recent Event Lists
    recent_events: List[Dict[str, str]] = field(default_factory=list)


class RealtimeEngine:
    """
    Master Real-Time SIGINT Monitoring Engine.
    Executes independent concurrent acquisition and DSP threads.
    """

    def __init__(
        self,
        config: Optional[HardwareConfig] = None,
        synthetic_rf: bool = False,
        synthetic_audio: bool = False,
        data_dir: str = "data",
    ):
        self.config = config or HardwareConfig()
        self.synthetic_rf = synthetic_rf
        self.synthetic_audio = synthetic_audio
        self.data_dir = data_dir

        # Ensure storage directory structure exists
        self._init_storage()

        # Hardware capture devices
        self.rf_device = RFCaptureDevice(
            config=self.config.rf,
            synthetic_mode=self.synthetic_rf,
        )
        self.acoustic_device = AcousticCaptureDevice(
            config=self.config.acoustic,
            synthetic_mode=self.synthetic_audio,
        )

        # DSP Processors
        self.rf_processor = RFProcessor(self.config.rf)
        self.acoustic_processor = AcousticProcessor(self.config.acoustic)

        # Detectors
        self.rf_detector = RFDetector(self.config.rf)
        self.acoustic_detector = AcousticDetector(self.config.acoustic)
        self.morse_detector = RealtimeMorseDetector(self.config.morse)

        # Threading and control
        self._is_running = threading.Event()
        self._is_paused = threading.Event()
        self._rf_thread: Optional[threading.Thread] = None
        self._acoustic_thread: Optional[threading.Thread] = None

        # Telemetry & State
        self._start_time: float = 0.0
        self._telemetry = EngineTelemetry()
        self._telemetry_lock = threading.Lock()
        self._recent_events_deque: Deque[Dict[str, str]] = deque(maxlen=20)

        # Callbacks for live notifications
        self._event_callbacks: List[Callable[[str, dict], None]] = []

    @property
    def is_running(self) -> bool:
        return self._is_running.is_set()

    @property
    def is_paused(self) -> bool:
        return self._is_paused.is_set()

    def register_event_callback(self, cb: Callable[[str, dict], None]) -> None:
        self._event_callbacks.append(cb)

    def _init_storage(self) -> None:
        """Create structured directory paths for logging and snapshots."""
        subdirs = [
            "rf/raw", "rf/processed", "rf/metadata",
            "acoustic/raw", "acoustic/processed", "acoustic/metadata",
            "mock_fan/audio", "mock_fan/rpm", "mock_fan/metadata",
            "events",
            "plots/rf_spectrum", "plots/rf_waterfall",
            "plots/acoustic_waveform", "plots/acoustic_spectrogram",
        ]
        for sub in subdirs:
            os.makedirs(os.path.join(self.data_dir, sub), exist_ok=True)

    def start(self) -> bool:
        """Start acquisition and DSP workers."""
        if self._is_running.is_set():
            return True

        self._start_time = time.time()
        self._is_running.set()
        self._is_paused.clear()

        # Start hardware captures
        self.rf_device.start()
        self.acoustic_device.start()

        # Start DSP worker threads
        self._rf_thread = threading.Thread(
            target=self._rf_worker_loop,
            name="AetherHound-RF-DSP-Worker",
            daemon=True,
        )
        self._acoustic_thread = threading.Thread(
            target=self._acoustic_worker_loop,
            name="AetherHound-Acoustic-DSP-Worker",
            daemon=True,
        )

        self._rf_thread.start()
        self._acoustic_thread.start()

        self._log_system_event("EngineStarted", "AetherHound dual-channel monitoring active")
        return True

    def pause(self) -> None:
        self._is_paused.set()
        self._log_system_event("EnginePaused", "Signal monitoring paused by user")

    def resume(self) -> None:
        self._is_paused.clear()
        self._log_system_event("EngineResumed", "Signal monitoring resumed by user")

    def stop(self) -> None:
        """Stop all pipelines gracefully."""
        self._is_running.clear()

        self.rf_device.stop()
        self.acoustic_device.stop()

        if self._rf_thread is not None and self._rf_thread.is_alive():
            self._rf_thread.join(timeout=1.0)
        if self._acoustic_thread is not None and self._acoustic_thread.is_alive():
            self._acoustic_thread.join(timeout=1.0)

        self._log_system_event("EngineStopped", "AetherHound engine halted cleanly")

    def get_telemetry(self) -> EngineTelemetry:
        """Thread-safe snapshot of live telemetry."""
        with self._telemetry_lock:
            self._telemetry.uptime_sec = time.time() - self._start_time if self._start_time > 0 else 0.0
            self._telemetry.rf_connected = self.rf_device.is_connected
            self._telemetry.mic_connected = self.acoustic_device.is_connected
            self._telemetry.is_paused = self._is_paused.is_set()
            self._telemetry.recent_events = list(self._recent_events_deque)
            return self._telemetry

    def _rf_worker_loop(self) -> None:
        """Independent worker loop for RF signal processing and anomaly detection."""
        while self._is_running.is_set():
            if self._is_paused.is_set():
                time.sleep(0.05)
                continue

            window = self.rf_device.get_window(timeout=0.2)
            if window is None:
                continue

            t0 = time.perf_counter()
            # Run DSP pipeline
            proc_win = self.rf_processor.process_window(window)

            # Run RF anomaly detector
            alert = self.rf_detector.update(proc_win)
            latency_ms = (time.perf_counter() - t0) * 1000.0

            # Update telemetry
            with self._telemetry_lock:
                self._telemetry.rf_center_freq_hz = window.center_freq_hz
                self._telemetry.rf_sample_rate_hz = window.sample_rate_hz
                self._telemetry.rf_queue_fill = self.rf_device.queue.qsize()
                self._telemetry.rf_dropped_windows = self.rf_device.dropped_count
                self._telemetry.rf_processing_latency_ms = round(latency_ms, 2)
                self._telemetry.rf_windows_processed = proc_win.window_id
                self._telemetry.rf_noise_floor_db = round(proc_win.noise_floor_db, 2)
                self._telemetry.rf_peak_power_db = round(proc_win.max_peak_power_db, 2)
                self._telemetry.rf_peak_freq_hz = round(proc_win.max_peak_freq_hz, 1)

                if alert:
                    self._telemetry.rf_status = "SUSPICIOUS"
                    self._handle_rf_alert(alert)
                else:
                    self._telemetry.rf_status = "NORMAL"

    def _acoustic_worker_loop(self) -> None:
        """Independent worker loop for Acoustic processing, bursts, and Morse detection."""
        while self._is_running.is_set():
            if self._is_paused.is_set():
                time.sleep(0.05)
                continue

            chunk = self.acoustic_device.get_chunk(timeout=0.2)
            if chunk is None:
                continue

            t0 = time.perf_counter()
            # Run DSP pipeline
            proc_chunk = self.acoustic_processor.process_chunk(chunk)

            # Run Acoustic anomaly detector
            acoustic_alert = self.acoustic_detector.update(proc_chunk)

            # Run Real-Time Morse detector
            morse_alert = self.morse_detector.process_chunk(proc_chunk)

            latency_ms = (time.perf_counter() - t0) * 1000.0

            # Update telemetry
            with self._telemetry_lock:
                self._telemetry.acoustic_sample_rate_hz = chunk.sample_rate_hz
                self._telemetry.acoustic_queue_fill = self.acoustic_device.queue.qsize()
                self._telemetry.acoustic_dropped_chunks = self.acoustic_device.dropped_count
                self._telemetry.acoustic_processing_latency_ms = round(latency_ms, 2)
                self._telemetry.acoustic_chunks_processed = proc_chunk.chunk_id
                self._telemetry.acoustic_rms_energy = round(proc_chunk.features.rms_energy, 5)
                self._telemetry.acoustic_dominant_freq_hz = round(proc_chunk.features.dominant_frequency_hz, 1)

                if acoustic_alert:
                    self._telemetry.acoustic_status = "SUSPICIOUS"
                    self._handle_acoustic_alert(acoustic_alert)
                else:
                    self._telemetry.acoustic_status = "NORMAL"

                if morse_alert:
                    self._telemetry.morse_status = "PATTERN DETECTED"
                    self._handle_morse_alert(morse_alert)
                elif self._telemetry.morse_status == "PATTERN DETECTED":
                    # Keep pattern alert sticky for a few seconds
                    pass

    def _handle_rf_alert(self, alert: RFAlertEvent) -> None:
        event_dict = {
            "timestamp": time.strftime("%H:%M:%S", time.localtime(alert.timestamp)),
            "sensor": alert.sensor_id,
            "event": alert.event_type,
            "evidence": f"Peak {alert.signal_power_db} dB at {alert.detected_freq_hz / 1e6:.3f} MHz (+{alert.deviation_db} dB)",
        }
        self._recent_events_deque.append(event_dict)
        self._write_jsonl("rf_events.jsonl", asdict(alert))
        for cb in self._event_callbacks:
            try:
                cb("RF_ALERT", asdict(alert))
            except Exception:
                pass

    def _handle_acoustic_alert(self, alert: AcousticAlertEvent) -> None:
        event_dict = {
            "timestamp": time.strftime("%H:%M:%S", time.localtime(alert.timestamp)),
            "sensor": alert.sensor_id,
            "event": alert.event_type,
            "evidence": f"Freq {alert.dominant_frequency_hz} Hz, Pulses: {alert.pulse_count}, RMS {alert.rms_energy}",
        }
        self._recent_events_deque.append(event_dict)
        self._write_jsonl("acoustic_events.jsonl", asdict(alert))
        for cb in self._event_callbacks:
            try:
                cb("ACOUSTIC_ALERT", asdict(alert))
            except Exception:
                pass

    def _handle_morse_alert(self, alert: MorsePatternEvent) -> None:
        event_dict = {
            "timestamp": time.strftime("%H:%M:%S", time.localtime(alert.timestamp)),
            "sensor": alert.sensor_id,
            "event": f"SOS Pattern ({alert.source})",
            "evidence": f"Morse: {alert.decoded_morse} (Conf: {alert.match_score * 100:.1f}%)",
        }
        self._recent_events_deque.append(event_dict)
        self._write_jsonl("morse_events.jsonl", asdict(alert))
        for cb in self._event_callbacks:
            try:
                cb("MORSE_ALERT", asdict(alert))
            except Exception:
                pass

    def _log_system_event(self, action: str, details: str) -> None:
        entry = {
            "timestamp": time.time(),
            "iso_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "action": action,
            "details": details,
        }
        self._write_jsonl("system_events.jsonl", entry)

    def _write_jsonl(self, filename: str, payload: dict) -> None:
        """Append record to designated JSONL file safely."""
        path = os.path.join(self.data_dir, "events", filename)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
        except Exception:
            pass
