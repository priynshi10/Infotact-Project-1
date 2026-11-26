# AetherHound Architecture

## Runtime flow

1. Acquisition enters through `aetherhound/hardware/rf_capture.py` or `aetherhound/hardware/acoustic_capture.py`.
2. `RFCaptureDevice` and `AcousticCaptureDevice` place bounded timestamped windows in queues.
3. `aetherhound/core/realtime_engine.py` dispatches independent RF and acoustic worker loops.
4. DSP processors in `aetherhound/dsp/` apply filtering, FFT/PSD/STFT and bounded waterfalls.
5. Existing statistical RF/acoustic/Morse detectors classify current windows.
6. Optional offline ML is implemented in `aetherhound/detection/anomaly_detector.py`.
7. The Rich monitor in `aetherhound/interface/live_monitor.py` renders snapshots and recent events.
8. Evidence and alerts are written beneath `data/events/` and acquisition metadata is written beside captures.

## Signal provenance

`LIVE_HARDWARE`, `RECORDED_HARDWARE`, and `SYNTHETIC_SIMULATION` are canonical source types from `aetherhound/core/evidence_metadata.py`. Synthetic CLI output must retain source metadata and must not be described as hardware capture.

## Backends

The supported software backend is NumPy/SciPy. GNU Radio remains optional. `SignalProcessingFlowgraph.backend` and `aetherhound/scripts/capability_check.py` report whether GNU Radio is available. A detected package alone does not mean native execution occurred.

The ML path has explicit `numpy_baseline` and `pytorch_autoencoder` selectors. Existing NumPy models remain loadable; PyTorch checkpoints are CPU state dictionaries plus a separate JSON metadata record.

## Virtual hardware path

`aetherhound/hardware/virtual_sdr.py` provides receive-only deterministic IQ generation and `.npy`/`.npz` playback. Every window is labelled `VIRTUAL_SDR`, uses a bounded queue and can feed `RFProcessor` directly.

GNU Radio selection is explicit: `python`, `gnuradio`, or `auto`. Native mode requires an importable GNU Radio package and receives synthetic IQ through a vector source. The active Windows environment does not provide GNU Radio, so Python DSP remains the tested fallback.

ARM64 deployment is static and Windows-safe. `deploy/aetherhound.service` and shell scripts provide headless/systemd startup. They are deployment templates, not proof of Raspberry Pi runtime execution.
