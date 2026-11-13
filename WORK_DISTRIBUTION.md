# INFOTACT SOLUTIONS - INTERNSHIP WORK DISTRIBUTION DOCUMENT

**Project Name:** AetherHound: Air-Gapped RF & Acoustic Covert Channel Detector  
**Intern Name:** Bharanidharan D  
**Intern Role:** Security Admin Associate L1. Intern  
**Intern Domain:** Cyber Security  
**Reference No.:** ITS/CS/1193  
**Start Date:** 11/05/2026 | **End Date:** 12/05/2026  
**Document Status:** Approved & Finalized for Mid-Project & Final Reviews  

---

## 1. Executive Summary & Project Assignment

As specified in the Project Assignment Letter and the *Infotact Project Execution Handbook V2.0*, each project comprises **4 week-wise implementations** culminating in a Mid-Project Review (Weeks 1 & 2) and a Final Project Review (Weeks 3 & 4). 

This document defines the comprehensive engineering and research work breakdown executed by Bharanidharan D as a dedicated security engineer and solo worker on the AetherHound system.

---

## 2. Week-Wise Implementation & Task Allocation

```
+----------------------------------------------------------------------------------------------------+
|                                    4-WEEK IMPLEMENTATION ROADMAP                                   |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  WEEK 1: Hardware Abstraction & Offensive Covert Channel Prototyping                              |
|  ├── Task 1.1: Audio receiver & microphone array abstraction layer (48 kHz / 96 kHz)               |
|  ├── Task 1.2: Software Defined Radio (SDR) complex IQ receiver interface (HackRF / RTL-SDR)       |
|  ├── Task 1.3: Physical server room acoustic & RF hum emulator with blade harmonics                |
|  └── Task 1.4: Benign CPU fan pulse malware (Fansmitter) with Morse code & binary modulation       |
|                                                                                                    |
|  WEEK 2: Signal Filtering, DSP Pipeline & High-Speed Terminal UI                                  |
|  ├── Task 2.1: 4th-order zero-phase Butterworth bandpass & 50/60 Hz power line notch filters       |
|  ├── Task 2.2: Hann-windowed STFT spectrogram generator & rolling waterfall matrix buffer          |
|  ├── Task 2.3: Peak frequency tracking, SNR calculation, and spectral kurtosis diagnostics         |
|  ├── Task 2.4: Hacker-style Rich dark-mode terminal dashboard updating at 30+ FPS                  |
|  └── Task 2.5: [MID-PROJECT REVIEW] Capture Validation: Proving frequency spike isolation          |
|                                                                                                    |
|  WEEK 3: Deep Neural Autoencoder Training & Incident Alerting Engine                              |
|  ├── Task 3.1: Convolutional-Recurrent PyTorch Autoencoder architecture design (32-dim latent)     |
|  ├── Task 3.2: Unsupervised training on baseline server hum with spectral continuity loss          |
|  ├── Task 3.3: Dynamic statistical anomaly thresholding (Mean + 2.5 * StdDev)                     |
|  ├── Task 3.4: Multi-sensor spatial triangulation engine (indoor Log-Distance Path Loss RSSI)     |
|  └── Task 3.5: Terminal red alert trigger, edge hardware piezo buzzer pulse, and JSONL logging     |
|                                                                                                    |
|  WEEK 4: Optimization, SIGINT Demodulation, Verification & Reporting                              |
|  ├── Task 4.1: Vectorized C-level matrix DSP math optimization (<1 ms execution time)              |
|  ├── Task 4.2: Covert channel signal demodulator (Morse code / binary ASCII recovery)             |
|  ├── Task 4.3: Comprehensive test suite (16 automated unit & integration tests)                    |
|  ├── Task 4.4: Model benchmark metrics calculation (ROC curve, AUC, PR curve, Confusion Matrix)    |
|  └── Task 4.5: [FINAL REVIEW] Production technical report, presentation deck, and live demo        |
+----------------------------------------------------------------------------------------------------+
```

---

## 3. Detailed Weekly Milestone Deliverables

### Week 1: Sensor Ingestion & Offensive Simulation (5th – 11th)
- **Module Deliverables:**
  - `aetherhound/sensors/base.py`: Abstract `SignalSource` interface.
  - `aetherhound/sensors/audio_receiver.py`: PortAudio/ALSA hardware capture interface.
  - `aetherhound/sensors/sdr_receiver.py`: Complex IQ radio interface.
  - `aetherhound/sensors/emulator.py`: High-fidelity multi-blade acoustic & RF physics simulator.
  - `aetherhound/malware/fansmitter.py`: Benign Morse code fan modulation script.
  - `aetherhound/malware/rambo_rf.py`: Benign RAM bus modulation script.
- **Verification:** Unit tests `tests/test_sensors.py` and `tests/test_malware.py` pass.

### Week 2: DSP Flowgraph, Terminal Interface & Mid Review (12th – 18th)
- **Module Deliverables:**
  - `aetherhound/dsp/filters.py`: Zero-phase bandpass, notch, and whitening filters.
  - `aetherhound/dsp/spectral.py`: STFT spectrogram generator with rolling waterfall.
  - `aetherhound/dsp/detector_dsp.py`: Peak frequency tracker, local SNR estimator.
  - `aetherhound/cli/hacker_terminal.py`: Terminal interface operating at 30+ FPS.
  - `aetherhound/malware/exfil_test_runner.py`: Validation script proving tone isolation.
- **Milestone Audit:**
  - Proved isolation of 1950 Hz fan malware with 48.9 dB SNR and 0% false positives.
  - Terminal UI confirmed operating at 30+ frames per second without memory leaks.

### Week 3: PyTorch ML Autoencoder & Triangulation (19th – 25th)
- **Module Deliverables:**
  - `aetherhound/ml/autoencoder.py`: Deep Conv2D-ConvTranspose2D spectral autoencoder.
  - `aetherhound/ml/dataset.py`: Spectrogram data synthesis, augmentation, and tensor pipeline.
  - `aetherhound/ml/evaluator.py`: Reconstruction error scoring and dynamic thresholding.
  - `aetherhound/engine/triangulator.py`: 4-sensor RSSI triangulation engine.
  - `aetherhound/engine/alert_manager.py`: Incident dispatcher and structured JSONL logging.
- **Milestone Audit:**
  - Autoencoder successfully trained on baseline hum with loss decreasing from 0.106 to 0.007.
  - Pinpointing algorithm accurately identifies `Rack-Delta` with 85%+ confidence.

### Week 4: SIMD Optimization, Demodulation & Final Review (26th – 4th)
- **Module Deliverables:**
  - `aetherhound/dsp/accelerated_dsp.py`: Vectorized C-memory layout routines ($<1\text{ ms}$).
  - `aetherhound/engine/demodulator.py`: Plaintext payload recovery (`FLAG{AIR_GAP_1337}`).
  - `aetherhound/engine/coordinator.py`: Master pipeline integration hub.
  - `run_demo.py`: Turnkey automated and interactive demonstration.
  - `train_model.py`: Model training and figure generation pipeline.
- **Final Audit & Deliverables:**
  - Model evaluation figures: `roc_curve.png`, `precision_recall_curve.png`, `confusion_matrix.png`.
  - Comprehensive Project Report: `PROJECT_REPORT.md` and compiled `PROJECT_REPORT.pdf`.
  - Executive Slide Deck: `presentation/AetherHound_Presentation.pptx`.

---

## 4. GitHub Compliance & Solo Contributor Attestation

Per Section 4.2 and Section 4.4 of the *Infotact Project Execution Handbook V2.0*:
> *"Solo Worker: If you are working alone on the project, you are allowed to commit directly to the main branch (no separate individual branch is required). Single person works individually and commits daily (20 days for final review)."*

All source code, documentation, test suites, and evaluation artifacts have been authored, verified, and committed by Bharanidharan D (`bharani2246@gmail.com`).
