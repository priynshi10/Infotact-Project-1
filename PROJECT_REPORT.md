# INFOTACT SOLUTIONS
## TECHNICAL PROJECT REPORT

**PROJECT TITLE:**  
# AetherHound: Air-Gapped RF & Acoustic Covert Channel Detector

**INTERNSHIP DOMAIN:** Cyber Security  
**INTERNSHIP ROLE:** Security Admin Associate L1. Intern  
**INTERN NAME:** Bharanidharan D  
**INTERN EMAIL:** bharani2246@gmail.com | **PHONE:** +91 9629908389  
**ORGANIZATION:** Infotact Solutions, Electronic City, Bengaluru, Karnataka, PN 560100  
**DOCUMENT REFERENCE:** ITS/CS/1193  
**START DATE:** 11/05/2026 | **END DATE:** 12/05/2026  
**SUBMISSION CYCLE:** Month 1 Final Project Review  

---

## ABSTRACT

In highly classified defense installations, air-gapped financial databases, and critical national infrastructure, compute clusters are physically severed from all conventional data networks (Ethernet, 802.11 Wi-Fi, Bluetooth, and cellular) to eliminate external cyber attack vectors. Despite this isolation, advanced persistent threats (APTs) have developed physical-layer side-channel exfiltration vectors—most notably manipulating internal chassis CPU fan speed pulse-width modulation (Fansmitter) or memory bus clock switching (RAMBO) to radiate acoustic Morse code and electromagnetic radio frequencies across the physical air-gap to nearby adversary receivers.

This report presents **AetherHound**, an autonomous, hyper-local edge appliance and signals intelligence (SIGINT) defense architecture designed to defeat physical-layer covert channel exfiltration. Operating entirely on offline, air-gapped embedded edge hardware without external network or cloud dependencies, AetherHound combines a multichannel acoustic and ultrasonic microphone array with a Software Defined Radio (SDR) receiver. 

The system implements a real-time digital signal processing (DSP) pipeline incorporating zero-phase 4th-order Butterworth bandpass filtering, mains power harmonic notch rejection, and windowed Short-Time Fourier Transforms (STFT). An unsupervised deep convolutional-recurrent spectral autoencoder neural network, trained solely on normal server-room acoustic and electromagnetic hum, learns baseline structural harmonics and detects artificial covert channels through reconstruction loss spikes and adaptive statistical thresholding ($\tau = \mu + 2.5\sigma$). 

Furthermore, AetherHound integrates a multi-sensor indoor log-distance path loss spatial triangulation engine that isolates the physical server rack transmitting the covert signals with $>85\%$ confidence, paired with an automated demodulation engine that reconstructs leaked payloads. Experimental evaluation across 250 test frames demonstrated a Receiver Operating Characteristic Area Under the Curve (ROC-AUC) of **0.9167**, Precision-Recall AUC of **0.9430**, **98.95%** precision, and an **0.8%** false positive rate, executing with sub-millisecond DSP latency and sustaining a real-time 30+ frames-per-second tactical console display.

---

## 1. INTRODUCTION & PROBLEM FORMULATION

### 1.1 The Air-Gap Security Paradigm
The concept of the "air-gap" has long represented the ultimate security boundary for sensitive computing systems. Air-gapped machines are physically isolated, lacking network interface cards (NICs), wireless adapters, and direct external cable connections. Prominent use cases include:
- Nuclear reactor instrumentation and Supervisory Control and Data Acquisition (SCADA) networks.
- Military command, control, communications, and intelligence ($C^3I$) computers.
- Hardware Security Modules (HSMs) generating root cryptographic authority certificates.
- Financial settlement clearing engines and isolated cold-storage cryptocurrency vaults.

### 1.2 Physical-Layer Covert Channel Exfiltration
While traditional perimeter network defenses prevent direct network access, malware can still bridge the air-gap via infected removable USB media (as demonstrated by the Stuxnet and Agent.BTZ campaigns), malicious hardware implants, or compromised firmware in supply chain components. Once an air-gapped server is infected, malware must solve the problem of exfiltrating confidential data (passwords, private encryption keys, telemetry) without standard network interfaces.

To achieve this, state-sponsored malware modulates the host hardware’s internal physical components:
1. **Acoustic Modulation (Fansmitter & DiskFiltration):** Malware controls CPU/GPU cooling fan rotational velocities via motherboard Pulse-Width Modulation (PWM) registers or schedules CPU-intensive compute threads. By accelerating and decelerating the fan, the emitted acoustic tone shifts frequencies (Frequency-Shift Keying - FSK) or pulses on and off (On-Off Keying - OOK / Morse code), broadcasting data acoustically to a hidden recording device or compromised smartphone up to 8 meters away.
2. **Electromagnetic RF Radiation (RAMBO & AirHopper):** Malware rapidly reads and writes data across memory channels. High-frequency electrical switching on the memory bus acts as an unintentional radio transmitter, radiating radio-frequency (RF) signals in the HF/VHF bands (24 MHz – 40 MHz) that can be picked up through walls by a nearby Software Defined Radio (SDR).

### 1.3 The Failure of Conventional IT Security
Traditional Information Security (InfoSec) tools—such as firewalls, web application firewalls (WAFs), and Network Intrusion Detection Systems (NIDS)—rely exclusively on parsing packet headers and payloads. Because physical covert channels bypass the network protocol stack entirely, conventional IT defenses are completely blind to them. Furthermore, server rooms are noisy, chaotic acoustic environments where blade servers run at 800 to 4500 RPM alongside heavy cooling HVAC units. Isolating a faint, structured 1-15 bps covert transmission buried inside this acoustic noise floor requires advanced Signals Intelligence (SIGINT) and machine learning.

---

## 2. AETHERHOUND SYSTEM DESIGN & ARCHITECTURE

AetherHound acts as a specialized "Physical-Layer Firewall and SIGINT Sentry" deployed directly inside the server room. It operates hyper-locally on dedicated edge compute hardware without cloud connectivity, web servers, or external network interfaces.

```
+----------------------------------------------------------------------------------------------------+
|                                    AETHERHOUND SYSTEM TOPOLOGY                                     |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ PHYSICAL SERVER ROOM ENVIRONMENT ]                                                              |
|        ├── Normal Server Racks (Alpha to Zeta): Baseline Multi-Blade Fan Harmonics + HVAC           |
|        └── Compromised Target (Rack-Delta): Injecting Fansmitter Acoustic PWM & RAMBO RF           |
|                                                                                                    |
|  [ SENSOR INGESTION LAYER ]                                                                        |
|        ├── Multichannel Acoustic Array: 4-element microphone array (48 kHz / 96 kHz Ultrasonic)    |
|        ├── Software Defined Radio: HackRF One / RTL-SDR v4 (24.5 MHz - 433 MHz, 2.4 MSPS)          |
|        └── AirGapEnvironmentEmulator: High-fidelity physical acoustic & RF simulation engine       |
|                                                                                                    |
|  [ DIGITAL SIGNAL PROCESSING (DSP) PIPELINE ]                                                      |
|        ├── Pre-filtering: 4th-order Butterworth Bandpass (200 Hz - 20 kHz) & 50/60 Hz Notch        |
|        ├── Spectral Transform: 1024-point Hann STFT (46.875 Hz/bin) & Welch PSD                    |
|        ├── Feature Diagnostics: Peak Frequency Tracker, Local SNR Estimator, Spectral Kurtosis     |
|        └── Matrix Acceleration: C-contiguous aligned arrays achieving <1 ms processing latency     |
|                                                                                                    |
|  [ UNSUPERVISED MACHINE LEARNING ENGINE ]                                                          |
|        ├── PyTorch Deep Spectral Autoencoder: 3-layer Conv2D encoder (32-dim latent space)         |
|        ├── Training: Unsupervised learning on clean, normal server hum with spectral continuity    |
|        ├── Anomaly Metric: Reconstruction loss = MSE + 1.5 * max(residual)                         |
|        └── Dynamic Statistical Threshold: Tau = Mean + 2.5 * StdDev (99% Confidence Interval)      |
|                                                                                                    |
|  [ SPATIAL TRIANGULATION & INCIDENT RESPONSE ]                                                     |
|        ├── Multi-Sensor RSSI Triangulation: Indoor Log-Distance Path Loss model                    |
|        ├── Rack Pinpointer: Isolates infected server rack (Rack-Delta) with 85%+ confidence        |
|        ├── SIGINT Demodulator: Recovers exfiltrated Morse code / binary ASCII payload              |
|        └── Edge Alerting: JSONL audit logging, terminal red alert flashing, edge piezo buzzer      |
|                                                                                                    |
|  [ AIR-GAPPED USER INTERFACES ]                                                                    |
|        ├── Tactical Hacker Terminal: Rich-based dark-mode console updating at 30+ FPS              |
|        └── Headless Curses Interface: Low-overhead Linux console for embedded ARM devices          |
+----------------------------------------------------------------------------------------------------+
```

---

## 3. HARDWARE SPECIFICATIONS & SENSOR INGESTION

AetherHound is designed to be housed in a rugged, edge appliance enclosure placed centrally within the server room facility:
1. **Edge Processor:** Industrial Raspberry Pi 5 or Raspberry Pi 4 Model B equipped with a 64-bit Quad-Core ARM Cortex-A76 processor @ 2.4 GHz and 8 GB LPDDR4X SDRAM.
2. **Acoustic Sensor Array:** Seeed Studio ReSpeaker 4-Mic Circular Array v2.0 utilizing an XMOS XVF3000 voice processor with 24-bit delta-sigma ADCs. Configured for 48 kHz standard acoustic sampling and up to 96 kHz ultrasonic sampling with a sensitivity of -26 dBFS @ 1 kHz.
3. **Software Defined Radio (SDR):** Great Scott Gadgets HackRF One (1 MHz to 6 GHz RF coverage, 2.4 MSPS I/Q bandwidth) or RTL-SDR Blog V4 with built-in TCXO (0.5 PPM) and HF direct sampling.
4. **Physical Alarm Interface:** Active 5V piezoelectric sounder connected to Raspberry Pi GPIO Pin 18 (PWM), providing local audible alarms in the data center.

---

## 4. DIGITAL SIGNAL PROCESSING (DSP) METHODOLOGY

### 4.1 Frequency Domain Transformation
Streaming time-domain physical signals are segmented into 1024-point frames with a 75% overlap ($H = 256$ samples) and multiplied by a Hann window:

$$w[n] = 0.5 \left(1 - \cos\left(\frac{2\pi n}{N-1}\right)\right)$$

The Short-Time Fourier Transform (STFT) yields frequency spectra with a bin resolution of:

$$\Delta f = \frac{f_s}{N} = \frac{48000\text{ Hz}}{1024} = 46.875\text{ Hz}$$

### 4.2 Filtering & Harmonic Suppression
- **Butterworth Bandpass Filter:** A 4th-order zero-phase Butterworth filter suppresses subsonic building vibrations below 200 Hz and high-frequency noise above 20 kHz.
- **Notch Filters:** Mains electricity harmonics at 50 Hz, 60 Hz, 100 Hz, and 120 Hz are eliminated via cascaded Infinite Impulse Response (IIR) notch filters ($Q = 30$).
- **Max-Pool Spectral Decimation:** When downsampling the 513 FFT frequency bins down to the 64 bins expected by the neural network, linear decimation was proven to drop narrowband covert tones. AetherHound implements max-pooling across 8-bin blocks:
  $$P_{\text{pooled}}[t, j] = \max_{i \in [j \cdot 8, (j+1) \cdot 8 - 1]} P_{\text{raw}}[t, i]$$
  This guarantees that a single sharp carrier pulse (e.g. 1950 Hz) is preserved at 100% signal strength.

---

## 5. UNSUPERVISED MACHINE LEARNING & ANOMALY DETECTION

### 5.1 Deep Spectral Convolutional Autoencoder
AetherHound uses an unsupervised deep learning approach. Supervised classification fails in covert channel defense because adversaries can adopt arbitrary modulation frequencies. By training exclusively on clean server-room hum, the network learns the structural features of blade server fans and HVAC noise.

The network architecture comprises:
- **Input Layer:** 2D Spectrogram Patch of shape $(B, 1, 40, 64)$ representing 40 time slices and 64 frequency bins.
- **Encoder:** 3 successive Conv2d layers with kernel size $3 \times 3$, stride 2, and padding 1 (16, 32, and 64 filters), each followed by Batch Normalization and LeakyReLU(0.2).
- **Latent Bottleneck:** Dense linear projection compressing 2,560 features into a 32-dimensional latent vector $z$.
- **Decoder:** Dense expansion followed by 3 ConvTranspose2d layers mirroring the encoder, with a Sigmoid activation generating normalized reconstructed spectrograms $\hat{X} \in [0, 1]$.
- **Total Model Parameters:** 190,229 trainable weights, executing inference in 1.4 milliseconds on a single CPU core.

### 5.2 Objective Function & Anomaly Metric
The autoencoder is trained using a composite loss function penalizing pixel-wise Mean Squared Error and Spectral Gradient differences:

$$\mathcal{L}(X, \hat{X}) = \text{MSE}(X, \hat{X}) + 0.3 \cdot \text{MSE}\left(\nabla_f X, \nabla_f \hat{X}\right)$$

During real-time inference, covert channel pulses create localized high-energy residuals that are diluted if only averaged over 2,560 pixels. The anomaly metric incorporates the peak spectral residual:

$$\mathcal{E}_{\text{anomaly}} = \text{MSE}(X, \hat{X}) + 1.5 \cdot \max_{t, f} (X_{t, f} - \hat{X}_{t, f})^2$$

The dynamic detection threshold $\tau$ is statistically calibrated on baseline emissions:

$$\tau = \mu_{\text{baseline}} + 2.5 \cdot \sigma_{\text{baseline}}$$

An alert is triggered when $\mathcal{E}_{\text{anomaly}} > \tau$.

---

## 6. SPATIAL TRIANGULATION & SIGNAL DEMODULATION

### 6.1 Multi-Sensor RSSI Triangulation
AetherHound deploys 4 perimeter sensors (Sensor-North, Sensor-South, Sensor-East, Sensor-West) across an 8m x 6m data hall containing 6 server racks (Rack-Alpha to Rack-Zeta). Using the indoor **Log-Distance Path Loss model**:

$$\text{RSSI}(d) = P_0 - 10 \cdot n \cdot \log_{10}\left(\frac{d}{d_0}\right)$$

Where $n = 2.2$ is the path loss exponent. The system calculates an energy-weighted spatial centroid and isolates the nearest server rack. In experimental testing with the mock malware emitting from Rack-Delta (4.0m, 5.0m), AetherHound pinpointed Rack-Delta with $>85\%$ confidence.

### 6.2 SIGINT Demodulation Engine
Once an anomaly is flagged, the demodulation engine analyzes the peak carrier transitions:
- Measures pulse durations (0.2s for dots, 0.6s for dashes).
- Converts international Morse code sequences into ASCII text.
- Reconstructs binary FSK bitstreams into printable characters.
- Successfully intercepted and decoded test canary payloads: `FLAG{AIR_GAP_1337}`.

---

## 7. EXPERIMENTAL EVALUATION & RESULTS

AetherHound was evaluated against 250 test spectrogram patches (125 clean baseline server hum frames and 125 covert malware attack frames across multiple PWM frequencies and server rack locations).

### 7.1 Quantitative Performance Metrics

| Evaluation Metric | Measured Value | Industry Benchmark | Compliance Status |
| :--- | :--- | :--- | :--- |
| **ROC-AUC** | **0.9167** | $> 0.85$ | **EXCEEDED** |
| **PR-AUC** | **0.9430** | $> 0.85$ | **EXCEEDED** |
| **Classification Accuracy** | **87.2%** | $> 80.0\%$ | **EXCEEDED** |
| **Precision** | **98.95%** | $> 90.0\%$ | **EXCEEDED** |
| **Detection Recall** | **75.2%** | $> 70.0\%$ | **EXCEEDED** |
| **F1 Score** | **0.8545** | $> 0.80$ | **EXCEEDED** |
| **False Positive Rate (FPR)** | **0.8%** | $< 3.0\%$ | **EXCEEDED** |
| **DSP Frame Latency** | **0.82 ms** | $< 10.0\text{ ms}$ | **EXCEEDED** |
| **Neural Inference Latency** | **1.40 ms** | $< 20.0\text{ ms}$ | **EXCEEDED** |
| **Terminal UI Frame Rate** | **30+ FPS** | $\ge 30\text{ FPS}$ | **EXCEEDED** |

### 7.2 Generated Figure Artifacts
All experimental metrics and figures have been generated and archived in `evaluation_results/`:
- `roc_curve.png`: Receiver Operating Characteristic curve displaying clean separation with AUC = 0.9167.
- `precision_recall_curve.png`: Precision-Recall curve with average precision AP = 0.9430.
- `reconstruction_loss_distribution.png`: Histogram demonstrating clear mathematical margin between baseline server hum and covert channel attacks.
- `confusion_matrix.png`: Confusion matrix confirming 124 true negatives, 94 true positives, and only 1 false positive.
- `spectrogram_anomaly_detection.png`: Side-by-side spectrograms of baseline hum, active Fansmitter attack, and the reconstruction error residual heatmap.
- `metrics_summary.json`: Raw machine-readable benchmark metrics.

---

## 8. MILESTONE COMPLIANCE & HANDBOOK SOP ALIGNMENT

The project was executed in strict accordance with the *Infotact Project Execution Handbook V2.0* and the *Project Assignment Letter*:

| Implementation Week | Scheduled Tasks | Completed Deliverables | Audit Status |
| :--- | :--- | :--- | :--- |
| **Week 1** | Hardware Setup & Mock Malware | Audio/SDR abstraction (`audio_receiver.py`, `sdr_receiver.py`), server room physics emulator (`emulator.py`), benign Morse fan malware (`fansmitter.py`). | **COMPLETED** |
| **Week 2** | Signal Filtering & 30+ FPS CLI | DSP filters (`filters.py`), STFT engine (`spectral.py`), Rich tactical terminal UI (`hacker_terminal.py`). **Mid-Review Audit:** Proved isolation of 1950 Hz fan spike with 48.9 dB SNR and 0% false positives. | **VERIFIED & PASSED** |
| **Week 3** | Deep Autoencoder & Triangulation | PyTorch Autoencoder training (`train_model.py`), adaptive thresholding (`evaluator.py`), 4-sensor rack triangulator (`triangulator.py`), incident logger (`alert_manager.py`). | **COMPLETED** |
| **Week 4** | Optimization, Tests & Final Review | Accelerated C-level DSP routines (`accelerated_dsp.py`), payload demodulator (`demodulator.py`), 16/16 passing tests, technical report, and executive PPT. | **VERIFIED & PASSED** |

---

## 9. CONCLUSION & FUTURE SCOPE

AetherHound demonstrates that physical-layer side-channel exfiltration across air-gapped environments can be reliably detected, pinpointed, and decoded using edge-deployed signals intelligence and unsupervised deep neural networks. By operating completely offline without cloud dependencies, web browsers, or external networks, AetherHound maintains strict air-gap compliance while closing the critical security gap where traditional IT firewalls are blind.

Future engineering directions include:
1. **Active Acoustic Jamming:** Integrating smart ultrasonic white-noise transducers to dynamically jam covert fan frequencies upon detection.
2. **Optical Side-Channel Expansion:** Adding photodiode sensor arrays to monitor hard drive activity LED blinking exfiltration (xLED).
3. **Hardware ASIC Implementation:** Porting the DSP pipeline to FPGA or Coral Edge TPU hardware to achieve sub-100 microsecond detection latency.
