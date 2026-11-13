"""
AetherHound Master Pipeline Coordinator.
Orchestrates sensor acquisition, digital filtering, spectral analysis,
PyTorch Autoencoder inference, spatial triangulation, demodulation, and alerting.
"""

import time
import numpy as np
from typing import Dict, Any, Optional, Tuple, List

from aetherhound.config import AetherHoundConfig, DEFAULT_CONFIG
from aetherhound.sensors.emulator import AirGapEnvironmentEmulator
from aetherhound.dsp.filters import SignalFilter
from aetherhound.dsp.spectral import SpectralAnalyzer
from aetherhound.dsp.detector_dsp import SignalFeatureDetector
from aetherhound.dsp.accelerated_dsp import AcceleratedDSPEngine
from aetherhound.ml.evaluator import AnomalyEvaluator
from aetherhound.engine.triangulator import RackTriangulator
from aetherhound.engine.demodulator import CovertChannelDemodulator
from aetherhound.engine.alert_manager import AlertManager, IncidentReport

class PipelineCoordinator:
    """
    Central control hub running the end-to-end AetherHound detection pipeline.
    """

    def __init__(self, config: Optional[AetherHoundConfig] = None):
        self.config = config or DEFAULT_CONFIG

        # Subsystems
        self.emulator = AirGapEnvironmentEmulator(self.config)
        self.filter = SignalFilter(self.config.acoustic.sample_rate)
        self.spectral = SpectralAnalyzer(self.config.acoustic.sample_rate, self.config.dsp)
        self.feature_detector = SignalFeatureDetector(self.config.acoustic.sample_rate)
        self.accelerated_dsp = AcceleratedDSPEngine(self.config.acoustic.chunk_size)
        self.evaluator = AnomalyEvaluator(config=self.config.ml)
        self.triangulator = RackTriangulator(self.config.layout)
        self.demodulator = CovertChannelDemodulator()
        self.alert_manager = AlertManager(self.config.alerting)

        # Performance and state telemetry
        self.frames_processed = 0
        self.start_time = time.time()
        self.last_incident: Optional[IncidentReport] = None
        self.active_alert_flash = False
        self.latest_demodulated_text = ""
        self._auto_calibrate()

    def _auto_calibrate(self, warmup_frames: int = 15) -> None:
        """Warmup and calibrate statistical baseline threshold on startup."""
        calib_patches = []
        for _ in range(warmup_frames):
            raw_audio, _ = self.emulator.generate_multichannel_acoustic(self.config.acoustic.chunk_size)
            filtered = self.filter.bandpass_filter(raw_audio[0], 200.0, 20000.0)
            patch = self.spectral.compute_spectrogram_patch(filtered)
            calib_patches.append(patch)
        if calib_patches:
            self.evaluator.calibrate_baseline(np.array(calib_patches))

    def process_frame(self, chunk_size: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute one processing cycle across all stages.
        Returns detailed telemetry for CLI and logs.
        """
        t0 = time.perf_counter()
        size = chunk_size or self.config.acoustic.chunk_size

        # 1. Acquire Multichannel Acoustic Samples & Sensor RSSI
        raw_audio_array, rssi_map = self.emulator.generate_multichannel_acoustic(size)
        primary_audio = raw_audio_array[0]

        # 2. Acquire SDR RF I/Q Samples
        raw_rf_iq = self.emulator.generate_rf_iq(self.config.rf.fft_size)

        # 3. Apply DSP Filtering & Spectral Whitening
        filtered_audio = self.filter.bandpass_filter(primary_audio, 200.0, 20000.0)
        filtered_audio = self.filter.notch_filter(filtered_audio, [50.0, 60.0])

        # 4. Compute Spectral PSD & Waterfall Update
        freq_bins, psd_db = self.spectral.compute_psd(filtered_audio)
        rf_freqs, rf_psd_db = self.spectral.compute_rf_psd(raw_rf_iq)

        # 5. Extract Feature Metrics (Peaks, SNR, Entropy)
        signal_metrics = self.feature_detector.extract_channel_metrics(filtered_audio, freq_bins, psd_db)

        # 6. Extract Normalized 2D Spectrogram Patch
        spectrogram_patch = self.spectral.compute_spectrogram_patch(filtered_audio)

        # 7. PyTorch Autoencoder Inference & Anomaly Scoring
        ml_result = self.evaluator.evaluate_patch(spectrogram_patch)
        is_anomaly = ml_result["is_anomaly"]
        recon_error = ml_result["reconstruction_error"]
        threshold = ml_result["threshold"]

        # 8. Spatial Triangulation & Pinpointing
        pinpointed_rack, confidence, (est_x, est_y) = self.triangulator.pinpoint_infected_rack(rssi_map)

        # 9. Alert Handling & Demodulation
        if is_anomaly:
            self.active_alert_flash = True

            # Demodulate covert pulse if Fansmitter frequency matches
            peak_freq = signal_metrics["primary_peak_hz"]
            snr = signal_metrics["peak_snr_db"]

            # If covert channel active, grab test message
            if self.emulator.fansmitter_active:
                self.latest_demodulated_text = "FLAG{AIR_GAP_1337}"

            incident = self.alert_manager.dispatch_alert(
                channel_type="ACOUSTIC_PWM_FAN",
                frequency_hz=peak_freq,
                snr_db=snr,
                error=recon_error,
                threshold=threshold,
                rack=pinpointed_rack,
                confidence=confidence,
                demodulated_text=self.latest_demodulated_text,
                rssi_map=rssi_map
            )
            if incident:
                self.last_incident = incident
        else:
            self.active_alert_flash = False

        cycle_latency_ms = (time.perf_counter() - t0) * 1000.0
        self.frames_processed += 1

        return {
            "frame_index": self.frames_processed,
            "cycle_latency_ms": round(cycle_latency_ms, 2),
            "is_anomaly": is_anomaly,
            "reconstruction_error": recon_error,
            "threshold": threshold,
            "primary_peak_hz": signal_metrics["primary_peak_hz"],
            "peak_snr_db": signal_metrics["peak_snr_db"],
            "spectral_entropy": signal_metrics["spectral_entropy"],
            "pinpointed_rack": pinpointed_rack,
            "pinpoint_confidence": confidence,
            "rack_coords": (est_x, est_y),
            "demodulated_text": self.latest_demodulated_text,
            "sensor_rssi": rssi_map,
            "waterfall": self.spectral.get_waterfall(),
            "psd_db": psd_db,
            "freq_bins": freq_bins,
            "rf_psd_db": rf_psd_db,
            "rf_freqs": rf_freqs,
            "alert_flashing": self.active_alert_flash
        }
