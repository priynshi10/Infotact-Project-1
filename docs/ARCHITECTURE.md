# AetherHound: Architecture & System Design

**Project Name:** AetherHound: Air-Gapped RF & Acoustic Covert Channel Detector  
**Author / Intern:** Bharanidharan D (Security Admin Associate L1. Intern)  
**Organization:** Infotact Solutions  
**Domain:** Cyber Security / Hardware Security & Signals Intelligence (SIGINT)  

---

## 1. Executive Architecture Overview

Air-gapped compute clusters in sensitive defense, intelligence, and financial environments are physically disconnected from Ethernet, Wi-Fi, cellular, and Bluetooth interfaces to prevent exfiltration. However, advanced persistent threats (APTs) exploit physical emissions—specifically **CPU fan acoustic pulse modulation (Fansmitter)** and **RAM memory-bus electromagnetic radiation (RAMBO)**—to transmit secret cryptographic keys and passwords over the air.

**AetherHound** provides an autonomous, real-time, air-gapped detection and spatial localization appliance. Operating hyper-locally on headless edge hardware (e.g., industrial Raspberry Pi 4/5 or NVIDIA Jetson) without external network dependencies, AetherHound ingests multichannel acoustic and Software Defined Radio (SDR) RF spectrum, filters ambient server-room noise, applies unsupervised Deep Autoencoder neural inference to detect structured anomalies, pinpoints the infected server rack via spatial multilateration, and demodulates exfiltrated payloads.

```
+----------------------------------------------------------------------------------------------------+
|                                    AETHERHOUND ARCHITECTURE                                       |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ Physical Air-Gap Environment ]                                                                 |
|         |                                                                                          |
|         +---> Acoustic Signals (Microphone Array: 48 kHz / 96 kHz Ultrasonic)                      |
|         +---> RF Signals (SDR: HackRF One / RTL-SDR @ 24.5 MHz - 433 MHz)                          |
|                                                                                                    |
|  [ Ingestion & Hardware Abstraction Layer ] (aetherhound/sensors/)                                 |
|         |---> audio_receiver.py (ALSA / PortAudio / Virtual Stream)                                |
|         |---> sdr_receiver.py (librtlsdr / HackRF IQ Ingestion)                                    |
|         +---> emulator.py (High-Fidelity Server Room Acoustic/RF Physics Engine)                   |
|                                                                                                    |
|  [ Digital Signal Processing (DSP) Pipeline ] (aetherhound/dsp/)                                  |
|         |---> filters.py (Butterworth Bandpass, 50/60 Hz Notch, Spectral Whitening)                |
|         |---> spectral.py (Windowed STFT, Welch PSD, Rolling Waterfall Matrix)                     |
|         |---> detector_dsp.py (Peak Frequency Tracker, SNR Estimator, Spectral Kurtosis)           |
|         +---> accelerated_dsp.py (Vectorized C/SIMD Array Math, <1ms Frame Latency)                |
|                                                                                                    |
|  [ Machine Learning Anomaly Detection Engine ] (aetherhound/ml/)                                 |
|         |---> autoencoder.py (Deep Convolutional-Recurrent Spectral Autoencoder)                   |
|         |---> dataset.py (Baseline Spectrogram Extractor & Augmenter)                              |
|         |---> evaluator.py (Reconstruction Error Loss: MSE + Peak Residual, Dynamic Threshold)    |
|         +---> metrics.py (ROC-AUC, Precision-Recall, Confusion Matrix, Distribution Curves)        |
|                                                                                                    |
|  [ Spatial Localization & Demodulation Engine ] (aetherhound/engine/)                              |
|         |---> triangulator.py (Log-Distance Path Loss RSSI & TDoA Rack Pinpointer)                 |
|         |---> demodulator.py (Morse Code & Binary FSK/OOK Covert Payload Decoder)                  |
|         +---> alert_manager.py (JSONL Audit Logger, Edge GPIO Hardware Buzzer)                     |
|                                                                                                    |
|  [ Edge Operational Interfaces ] (aetherhound/cli/)                                               |
|         |---> hacker_terminal.py (Rich Dark-Mode Curses Terminal @ 30+ FPS)                        |
|         +---> curses_ui.py (Native Headless Linux Console Interface)                               |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Core Subsystems

### 2.1 Physical Ingestion & Sensor Array
- **Multichannel Acoustic Array:** Captures acoustic frequencies (200 Hz – 24 kHz) and near-ultrasonic ranges (up to 48 kHz with 96 kHz sampling). Multiple microphone elements spaced in a planar layout allow Time Difference of Arrival (TDoA) and RSSI spatial measurements.
- **Software Defined Radio (SDR):** Tuned to fundamental clock leakages (e.g., 24.5 MHz DDR memory bus harmonics, 433.92 MHz ISM band). Reads complex I/Q data streams at 2.4 MSPS.
- **AirGapEnvironmentEmulator:** High-fidelity simulation module modeling multi-blade server harmonics (320 Hz, 640 Hz, 960 Hz), chassis vibrations, cooling unit airflow, and active covert malware vectors.

### 2.2 Digital Signal Processing (DSP)
- **Zero-Phase Butterworth Filtering:** Filters frequencies outside the covert acoustic band (200 Hz to 20 kHz) to eliminate subsonic HVAC rumble and high-frequency transducer artifacts.
- **Power Grid Notch Rejection:** Notch filters at 50 Hz, 60 Hz, 100 Hz, and 120 Hz suppress electrical line hum.
- **Spectral Whitening & STFT:** Slices incoming data into 1024-point Hann-windowed frames with 75% overlap, generating high-resolution spectral waterfalls.
- **Accelerated C-Level Vectorization:** Uses contiguous C-aligned arrays and vector operations to ensure processing cycles take under 1 millisecond per frame, guaranteeing a fluid 30+ frames-per-second console refresh.

### 2.3 PyTorch Deep Spectral Autoencoder
- **Architecture:** 3-layer Convolutional Encoder with Batch Normalization and LeakyReLU activations compressing 2D spectrogram patches $(40 \times 64)$ into a 32-dimensional latent bottleneck, paired with a symmetrical ConvTranspose Decoder.
- **Training Strategy:** Unsupervised training exclusively on clean, normal server-room acoustic hum. The network learns the structural features of blade server fans and HVAC noise.
- **Anomaly Detection Metric:** When structured covert malware pulses (Fansmitter/RAMBO) appear, the network fails to compress the unnatural narrowband harmonic, causing a spike in reconstruction error:
  $$\mathcal{L}_{\text{anomaly}} = \text{MSE}(X, \hat{X}) + 1.5 \cdot \max_{t, f} |X_{t, f} - \hat{X}_{t, f}|^2$$
- **Adaptive Thresholding:** Threshold dynamically updates using a sliding statistical window:
  $$\tau = \mu_{\text{baseline}} + k \cdot \sigma_{\text{baseline}} \quad (k = 2.5)$$

### 2.4 Spatial Triangulation & Server Rack Pinpointing
- Uses the indoor **Log-Distance Path Loss model**:
  $$\text{RSSI}(d) = P_0 - 10 \cdot n \cdot \log_{10}(d / d_0)$$
- Correlates multi-sensor signal power with known coordinates of server racks (Rack-Alpha through Rack-Zeta). Calculates an energy-weighted centroid to isolate the physical server rack emitting the covert transmission.

### 2.5 Signal Demodulation & Capture Validation
- Extracts pulse timings and carrier transitions from the isolated frequency band.
- Implements an international Morse Code decoder and binary FSK/OOK demodulator, reconstructing leaked strings (e.g., `FLAG{AIR_GAP_1337}`) to prove complete capture validation.

---

## 3. Threat Model Coverage

| Covert Channel Vector | Physical Mechanism | Target Frequency Range | Detection Method |
| :--- | :--- | :--- | :--- |
| **Fansmitter** (Guri et al.) | CPU fan RPM / PWM modulation | 1000 Hz – 3000 Hz | Acoustic Autoencoder + Peak SNR Tracker |
| **DiskFiltration** | Hard drive actuator arm seek acoustics | 800 Hz – 2500 Hz | Spectrogram Kurtosis + Reconstruction Residual |
| **RAMBO** | RAM memory bus read/write cycle bursts | 24 MHz – 40 MHz RF | SDR IQ FFT + Spectral Kurtosis |
| **AirHopper** | GPU display line emissions | 90 MHz – 110 MHz FM | SDR Wideband Spectrogram Scanner |

---

## 4. Hardware Deployment Architecture

AetherHound is designed to operate on a self-contained edge appliance located centrally inside a server room:
- **Processor:** Broadcom BCM2711 / BCM2712 Quad-Core Cortex-A76 @ 2.4 GHz
- **Memory:** 4 GB / 8 GB LPDDR4X
- **Radio Interface:** HackRF One (1 MHz – 6 GHz) or RTL-SDR v4
- **Acoustic Interface:** 4-Channel ReSpeaker USB Mic Array v2.0
- **Alert System:** Local Active Piezo Buzzer on GPIO Pin 18 + Red Alert Terminal Display
