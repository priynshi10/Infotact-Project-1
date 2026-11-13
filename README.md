# AetherHound: Air-Gapped RF & Acoustic Covert Channel Detector

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-EE4C2C.svg)](https://pytorch.org/)
[![Domain](https://img.shields.io/badge/Domain-Cyber%20Security%20%2F%20SIGINT-red.svg)]()
[![License](https://img.shields.io/badge/License-Proprietary%20%7C%20Infotact%20Solutions-yellow.svg)]()
[![Tests](https://img.shields.io/badge/Tests-16%20Passed%20%28100%25%29-brightgreen.svg)]()
[![ROC-AUC](https://img.shields.io/badge/ROC--AUC-0.9167-success.svg)]()

> **Infotact Solutions — Advanced Cybersecurity Engineering Internship**  
> **Project 2 Assignment:** Air-Gapped RF & Acoustic Covert Channel Detector  
> **Intern:** Bharanidharan D (Security Admin Associate L1. Intern)  
> **Reference Number:** ITS/CS/1193  

---

## 1. Executive Summary

In high-security facilities (defense installations, nuclear SCADA control centers, financial cryptographic HSMs), servers are **air-gapped**—physically disconnected from Ethernet, Wi-Fi, cellular, and Bluetooth networks. Despite this isolation, advanced state-actors use malware to manipulate host physical components:
1. **Fansmitter (Acoustic):** Regulating CPU cooling fan PWM speeds to emit Morse code or FSK acoustic frequencies (1000 Hz – 3000 Hz) to an adversary's microphone.
2. **RAMBO (Electromagnetic):** Modulating memory bus read/write cycles to radiate HF/VHF radio emissions (24 MHz – 40 MHz) captured by nearby Software Defined Radios (SDR).

Traditional IT firewalls analyze packets and are completely blind to physical emissions. **AetherHound** is an autonomous, hyper-local, physical-layer Signals Intelligence (SIGINT) defense appliance deployed directly inside the server room on edge hardware (e.g. Raspberry Pi 5 / Jetson). Operating **100% offline without cloud connectivity or web servers**, AetherHound ingests multichannel acoustic and RF signals, filters server room noise, uses an unsupervised Deep Spectral Autoencoder to detect structured covert channels, pinpoints the infected server rack in real time via spatial triangulation, and demodulates exfiltrated payloads.

---

## 2. High-Level Architecture

```
+----------------------------------------------------------------------------------------------------+
|                                    AETHERHOUND ARCHITECTURE                                       |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ Physical Ingestion Layer ] (aetherhound/sensors/)                                               |
|         ├── 4-Channel Acoustic Microphone Array (48 kHz / 96 kHz Ultrasonic)                       |
|         ├── Software Defined Radio (HackRF One / RTL-SDR @ 24.5 MHz - 433 MHz)                     |
|         └── AirGapEnvironmentEmulator (Physics-based multi-blade hum & covert channel simulator)   |
|                                                                                                    |
|  [ Digital Signal Processing (DSP) Pipeline ] (aetherhound/dsp/)                                  |
|         ├── Zero-phase 4th-order Butterworth Bandpass Filter (200 Hz - 20 kHz)                     |
|         ├── Cascaded IIR Notch Filters (50/60/100/120 Hz power grid hum rejection)                 |
|         ├── 1024-point Hann STFT Spectrogram Generator & Rolling 2D Waterfall Buffer               |
|         ├── Max-Pooled Spectral Downsampler (preserves narrowband covert spikes)                   |
|         └── Vectorized Accelerated C-Memory Engine (sub-millisecond frame processing)              |
|                                                                                                    |
|  [ Unsupervised Deep Learning Anomaly Detection ] (aetherhound/ml/)                                |
|         ├── PyTorch Deep Spectral Convolutional Autoencoder (32-dim latent bottleneck)             |
|         ├── Trained exclusively on clean, normal server-room acoustic/RF hum                       |
|         ├── Anomaly Loss Metric: Error = MSE(X, X_hat) + 1.5 * max(residual)                       |
|         └── Adaptive Statistical Threshold: Tau = Mean_baseline + 2.5 * Std_baseline               |
|                                                                                                    |
|  [ Spatial Localization & Demodulation Engine ] (aetherhound/engine/)                              |
|         ├── Indoor Log-Distance Path Loss RSSI Triangulation (isolates infected rack with >85% conf)|
|         ├── Covert Signal Demodulator (reconstructs Morse code & binary ASCII payloads)            |
|         └── Alert Manager (JSONL audit logging, terminal red alert, edge GPIO piezo buzzer)        |
|                                                                                                    |
|  [ Air-Gapped Tactical Interfaces ] (aetherhound/cli/)                                             |
|         ├── HackerTerminalUI: Rich dark-mode console updating at 30+ FPS                           |
|         └── CursesEdgeDashboard: Native Linux console for headless edge devices                     |
+----------------------------------------------------------------------------------------------------+
```

---

## 3. Repository Structure

```
INFOTACT/
├── aetherhound/                   # Core Python Package
│   ├── __init__.py                # Package version & metadata
│   ├── config.py                  # Global dataclass configuration
│   ├── sensors/                   # Hardware Ingestion Layer
│   │   ├── base.py                # Abstract SignalSource interface
│   │   ├── audio_receiver.py      # ALSA / PortAudio multichannel receiver
│   │   ├── sdr_receiver.py        # HackRF / RTL-SDR complex IQ receiver
│   │   └── emulator.py            # High-fidelity acoustic/RF physics emulator
│   ├── dsp/                       # Digital Signal Processing Pipeline
│   │   ├── filters.py             # Butterworth bandpass & notch filters
│   │   ├── spectral.py            # Windowed STFT & rolling waterfall matrix
│   │   ├── detector_dsp.py        # Peak frequency, SNR & kurtosis extractor
│   │   └── accelerated_dsp.py     # C-contiguous vectorized matrix operations
│   ├── ml/                        # Machine Learning Anomaly Engine
│   │   ├── autoencoder.py         # PyTorch Conv2d Deep Spectral Autoencoder
│   │   ├── dataset.py             # Spectrogram extraction & augmentation
│   │   ├── evaluator.py           # Anomaly scoring & adaptive thresholding
│   │   └── metrics.py             # ROC, PR, Confusion Matrix & plot generator
│   ├── engine/                    # Triangulation & Incident Response
│   │   ├── alert_manager.py       # JSONL audit logging & edge buzzer trigger
│   │   ├── triangulator.py        # Log-distance path loss rack pinpointer
│   │   ├── demodulator.py         # Morse code & binary FSK decoder
│   │   └── coordinator.py         # Master pipeline integration coordinator
│   ├── malware/                   # Offensive Proof-of-Concept Suite
│   │   ├── fansmitter.py          # Benign Morse CPU fan modulation tool
│   │   ├── rambo_rf.py            # Benign RAM bus RF modulation tool
│   │   └── exfil_test_runner.py   # Mid-Project Review capture validation audit
│   └── cli/                       # Air-Gapped Terminal Dashboards
│       ├── hacker_terminal.py     # Rich dark-mode tactical UI (@ 30+ FPS)
│       └── curses_ui.py           # Native headless Curses console
├── tests/                         # Automated Test Suite (16/16 Passed)
│   ├── test_sensors.py            # Sensor streaming & emulator tests
│   ├── test_dsp.py                # Filter & FFT mathematical validation
│   ├── test_ml.py                 # PyTorch forward pass & loss tests
│   ├── test_malware.py            # Mock malware modulation tests
│   ├── test_triangulation.py      # Spatial RSSI localization tests
│   ├── test_demodulator.py        # Morse & binary decoding tests
│   └── test_end_to_end.py         # Complete pipeline integration test
├── docs/                          # Comprehensive Technical Documentation
│   ├── ARCHITECTURE.md            # Deep system architecture & SIGINT design
│   ├── HARDWARE_SPECS.md          # Raspberry Pi, SDR, and mic array specs
│   ├── DSP_PIPELINE.md            # DSP equations, filter transfer functions
│   ├── ML_MODEL.md                # Neural network layers, loss, thresholds
│   ├── DEPLOYMENT_GUIDE.md        # Air-gapped setup & systemd service guide
│   └── THREAT_MODEL.md            # MITRE ATT&CK & air-gap attack taxonomy
├── evaluation_results/            # Generated Benchmark Artifacts
│   ├── autoencoder_best.pt        # Trained PyTorch neural network weights
│   ├── roc_curve.png              # ROC Curve (AUC = 0.9167)
│   ├── precision_recall_curve.png # PR Curve (AP = 0.9430)
│   ├── reconstruction_loss_distribution.png # Loss separation plot
│   ├── confusion_matrix.png       # 2x2 Anomaly classification matrix
│   ├── spectrogram_anomaly_detection.png # Spectrogram residual heatmap
│   └── metrics_summary.json       # Machine-readable performance metrics
├── presentation/                  # Executive Review Presentations
│   └── AetherHound_Presentation.pptx # 12-slide widescreen slide deck
├── WORK_DISTRIBUTION.md           # Mandatory task allocation document
├── PROJECT_REPORT.md              # Formal technical project report (Markdown)
├── PROJECT_REPORT.pdf             # Compiled publication-grade PDF report
├── run_demo.py                    # Turnkey demonstration runner
├── train_model.py                 # Model training and figure generator
├── requirements.txt               # Python package requirements
└── README.md                      # Master project README
```

---

## 4. Quick Start & Execution

### 4.1 Prerequisites & Installation
```bash
# Clone the repository
git clone https://github.com/Infotact-Solutions/AetherHound.git
cd AetherHound

# Install dependencies
python -m pip install -r requirements.txt
```

### 4.2 Run Full Verification Test Suite
```bash
python -m pytest tests/ -v
```
*Expected: 16 passed in ~8 seconds.*

### 4.3 Train Autoencoder & Generate Benchmark Figures
```bash
python train_model.py
```
*Trains the PyTorch Autoencoder on baseline server hum, calibrates dynamic threshold, evaluates test metrics, and exports all plots into `evaluation_results/`.*

### 4.4 Run Headless Demonstration (Audit Mode)
```bash
python run_demo.py
```
*Processes normal baseline frames, injects mock Fansmitter malware at Rack-Delta, isolates the 1950 Hz tone, triggers anomaly alert, pinpoints the rack, demodulates the canary payload `FLAG{AIR_GAP_1337}`, and logs to `logs/aetherhound_incidents.jsonl`.*

### 4.5 Run Interactive Hacker Terminal UI (@ 30+ FPS)
```bash
python run_demo.py --interactive
```

### 4.6 Execute Mid-Project Review Capture Validation
```bash
python -m aetherhound.malware.exfil_test_runner
```

---

## 5. Quantitative Experimental Evaluation

| Metric | AetherHound Measured | Benchmark Threshold | Status |
| :--- | :--- | :--- | :--- |
| **ROC-AUC** | **0.9167** | $> 0.8500$ | **EXCEEDED** |
| **PR-AUC** | **0.9430** | $> 0.8500$ | **EXCEEDED** |
| **Overall Accuracy** | **87.20%** | $> 80.00\%$ | **EXCEEDED** |
| **Precision** | **98.95%** | $> 90.00\%$ | **EXCEEDED** |
| **Detection Recall** | **75.20%** | $> 70.00\%$ | **EXCEEDED** |
| **F1 Score** | **0.8545** | $> 0.8000$ | **EXCEEDED** |
| **False Positive Rate (FPR)**| **0.80%** | $< 3.00\%$ | **EXCEEDED** |
| **DSP Processing Latency** | **0.82 ms** | $< 10.0\text{ ms}$ | **EXCEEDED** |
| **Neural Inference Latency** | **1.40 ms** | $< 20.0\text{ ms}$ | **EXCEEDED** |
| **Terminal Frame Rate** | **30+ FPS** | $\ge 30\text{ FPS}$ | **EXCEEDED** |

---

## 6. Review Deliverables Checklist

- [x] **Source Code:** Fully functioning, modular, object-oriented, PEP-8 compliant codebase under `aetherhound/`.
- [x] **Project Documentation:** Complete guides under `docs/` (`ARCHITECTURE.md`, `HARDWARE_SPECS.md`, `DSP_PIPELINE.md`, `ML_MODEL.md`, `DEPLOYMENT_GUIDE.md`, `THREAT_MODEL.md`).
- [x] **Project Report:** Professional formal report (`PROJECT_REPORT.md` and compiled `PROJECT_REPORT.pdf`).
- [x] **Presentation Deck:** Executive 12-slide PowerPoint presentation (`presentation/AetherHound_Presentation.pptx`).
- [x] **Model Evaluation Results:** Trained model weights and plots under `evaluation_results/` (`autoencoder_best.pt`, `roc_curve.png`, `precision_recall_curve.png`, `reconstruction_loss_distribution.png`, `confusion_matrix.png`, `spectrogram_anomaly_detection.png`, `metrics_summary.json`).
- [x] **Demonstration Executable:** Interactive and automated turnkey demo (`run_demo.py`).
- [x] **Work Distribution Document:** Completed task distribution document (`WORK_DISTRIBUTION.md`) aligned with Handbook guidelines.
- [x] **Mid-Project Review Audit:** Proved isolation of mock fan malware frequency spike with 48.9 dB SNR and 0% false positives (`exfil_test_runner.py`).

---

## 7. Author & License

- **Author:** Bharanidharan D
- **Role:** Security Admin Associate L1. Intern
- **Domain:** Cyber Security
- **Organization:** Infotact Solutions
- **Reference:** ITS/CS/1193
- **License:** Proprietary — All Rights Reserved by Infotact Solutions.
