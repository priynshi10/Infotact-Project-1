"""
AetherHound Acoustic Acquisition Module
Continuous real-time microphone acquisition using PyAudio callback streaming,
bounded queues, WAV recording, and synthetic test fallback.
"""

from dataclasses import dataclass
import os
import queue
import threading
import time
from typing import List, Optional, Tuple, Union

import numpy as np
import soundfile as sf

from aetherhound.hardware.config import AcousticConfig


@dataclass
class AudioChunk:
    """A timestamped chunk of audio samples."""
    samples: np.ndarray          # 1D float32 array in range [-1.0, 1.0]
    timestamp: float             # POSIX epoch timestamp
    sample_rate_hz: int
    channels: int
    is_synthetic: bool = False
    chunk_id: int = 0
    dropped_before: int = 0


class AcousticCaptureDevice:
    """
    Microphone acquisition controller using PyAudio non-blocking stream callback.
    """

    def __init__(
        self,
        config: Optional[AcousticConfig] = None,
        queue_size: int = 64,
        synthetic_mode: bool = False,
    ):
        self.config = config or AcousticConfig()
        self.config.validate()
        self.synthetic_mode = synthetic_mode

        self._queue: "queue.Queue[AudioChunk]" = queue.Queue(maxsize=queue_size)
        self._is_running = threading.Event()
        self._pyaudio_instance = None
        self._stream = None
        self._synthetic_thread: Optional[threading.Thread] = None

        self._dropped_chunks = 0
        self._chunk_counter = 0
        self._total_frames = 0
        self._last_error: Optional[str] = None
        self._connected = False

        # Optional recording buffer
        self._is_recording = False
        self._recording_buffer: List[np.ndarray] = []
        self._recording_lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._is_running.is_set()

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def queue(self) -> "queue.Queue[AudioChunk]":
        return self._queue

    @property
    def dropped_count(self) -> int:
        return self._dropped_chunks

    @property
    def total_frames(self) -> int:
        return self._total_frames

    def start(self) -> bool:
        """Start continuous acoustic acquisition."""
        if self._is_running.is_set():
            return True

        if not self.synthetic_mode:
            success = self._init_hardware_stream()
            if not success:
                # Fallback to synthetic if hardware fails
                return False
        else:
            self._connected = True

        self._is_running.set()

        if self.synthetic_mode:
            self._synthetic_thread = threading.Thread(
                target=self._synthetic_audio_loop,
                name="AetherHound-MicSyntheticWorker",
                daemon=True,
            )
            self._synthetic_thread.start()

        return True

    def stop(self) -> None:
        """Stop microphone streaming and clean up audio resources."""
        self._is_running.clear()

        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if self._pyaudio_instance is not None:
            try:
                self._pyaudio_instance.terminate()
            except Exception:
                pass
            self._pyaudio_instance = None

        if self._synthetic_thread is not None and self._synthetic_thread.is_alive():
            self._synthetic_thread.join(timeout=1.0)
            self._synthetic_thread = None

        self._connected = False

    def get_chunk(self, timeout: float = 0.5) -> Optional[AudioChunk]:
        """Fetch the next audio chunk from the queue."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def start_recording(self) -> None:
        """Start accumulating incoming samples into recording buffer for WAV export."""
        with self._recording_lock:
            self._recording_buffer = []
            self._is_recording = True

    def stop_and_save_recording(self, file_path: str) -> bool:
        """Stop accumulating and save recorded audio to a WAV file."""
        with self._recording_lock:
            self._is_recording = False
            if not self._recording_buffer:
                return False
            data = np.concatenate(self._recording_buffer, axis=0)
            self._recording_buffer = []

        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        sf.write(file_path, data, self.config.sample_rate_hz)
        return True

    def _init_hardware_stream(self) -> bool:
        """Initialize PyAudio input stream with non-blocking callback."""
        try:
            import pyaudio
            self._pyaudio_instance = pyaudio.PyAudio()

            # Format selection
            fmt = pyaudio.paFloat32 if self.config.audio_format == "float32" else pyaudio.paInt16

            def audio_callback(in_data, frame_count, time_info, status_flags):
                now = time.time()
                # Parse in_data to float32 numpy
                if fmt == pyaudio.paFloat32:
                    samples = np.frombuffer(in_data, dtype=np.float32)
                else:
                    int_samples = np.frombuffer(in_data, dtype=np.int16)
                    samples = int_samples.astype(np.float32) / 32768.0

                if self.config.channels == 2 and len(samples) > 0:
                    # Average stereo to mono for covert channel DSP
                    samples = samples.reshape(-1, 2).mean(axis=1)

                self._chunk_counter += 1
                self._total_frames += len(samples)

                chunk = AudioChunk(
                    samples=samples,
                    timestamp=now,
                    sample_rate_hz=self.config.sample_rate_hz,
                    channels=1,
                    is_synthetic=False,
                    chunk_id=self._chunk_counter,
                    dropped_before=self._dropped_chunks,
                )

                try:
                    self._queue.put_nowait(chunk)
                except queue.Full:
                    try:
                        self._queue.get_nowait()
                        self._queue.put_nowait(chunk)
                    except Exception:
                        pass
                    self._dropped_chunks += 1

                if self._is_recording:
                    with self._recording_lock:
                        self._recording_buffer.append(samples.copy())

                return (None, pyaudio.paContinue)

            stream_kwargs = {
                "format": fmt,
                "channels": self.config.channels,
                "rate": self.config.sample_rate_hz,
                "input": True,
                "frames_per_buffer": self.config.chunk_size,
                "stream_callback": audio_callback,
            }
            if self.config.device_index is not None:
                stream_kwargs["input_device_index"] = self.config.device_index

            self._stream = self._pyaudio_instance.open(**stream_kwargs)
            self._stream.start_stream()
            self._connected = True
            self._last_error = None
            return True

        except Exception as ex:
            self._connected = False
            self._last_error = f"PyAudio stream initialization failed: {ex}"
            return False

    def _synthetic_audio_loop(self) -> None:
        """
        Synthetic acoustic generator for hardware-independent test modes.
        Generates ambient server-room white noise + 120Hz electrical hum.
        """
        chunk_size = self.config.chunk_size
        sr = self.config.sample_rate_hz
        duration_per_chunk = chunk_size / sr
        rng = np.random.default_rng(seed=1337)
        phase = 0.0

        while self._is_running.is_set():
            loop_start = time.time()

            t = (np.arange(chunk_size) / sr) + phase
            phase = (phase + duration_per_chunk) % 1.0

            # Ambient acoustic noise (quiet room: -45 dBFS)
            ambient_noise = rng.normal(0, 0.005, chunk_size)
            # Low 120 Hz room / PSU transformer hum
            hum = 0.002 * np.sin(2 * np.pi * 120.0 * t)
            samples = (ambient_noise + hum).astype(np.float32)

            now = time.time()
            self._chunk_counter += 1
            self._total_frames += chunk_size

            chunk = AudioChunk(
                samples=samples,
                timestamp=now,
                sample_rate_hz=sr,
                channels=1,
                is_synthetic=True,
                chunk_id=self._chunk_counter,
                dropped_before=self._dropped_chunks,
            )

            try:
                self._queue.put_nowait(chunk)
            except queue.Full:
                try:
                    self._queue.get_nowait()
                    self._queue.put_nowait(chunk)
                except Exception:
                    pass
                self._dropped_chunks += 1

            if self._is_recording:
                with self._recording_lock:
                    self._recording_buffer.append(samples.copy())

            elapsed = time.time() - loop_start
            sleep_time = max(0.001, duration_per_chunk - elapsed)
            time.sleep(sleep_time)


def inject_synthetic_audio_pulse(
    chunk: AudioChunk,
    carrier_freq_hz: float = 1800.0,
    amplitude: float = 0.35,
) -> AudioChunk:
    """
    Utility for testing: injects a tonal acoustic burst into an AudioChunk.
    """
    n = len(chunk.samples)
    t = np.arange(n) / chunk.sample_rate_hz
    tone = amplitude * np.sin(2 * np.pi * carrier_freq_hz * t)
    mod_samples = np.clip(chunk.samples + tone.astype(np.float32), -1.0, 1.0)
    return AudioChunk(
        samples=mod_samples,
        timestamp=chunk.timestamp,
        sample_rate_hz=chunk.sample_rate_hz,
        channels=chunk.channels,
        is_synthetic=True,
        chunk_id=chunk.chunk_id,
        dropped_before=chunk.dropped_before,
    )
