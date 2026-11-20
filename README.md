<div align="center">

# AETHERHOUND

### Air-Gapped RF & Acoustic Covert Channel Detector

**Detect. Analyze. Investigate.**

A defensive cybersecurity research platform designed to monitor, analyze, and identify potential covert communication channels through electromagnetic and acoustic side-channel signals.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-Frontend-61DAFB?logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-Build-646CFF?logo=vite&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey)
![Status](https://img.shields.io/badge/Status-Research%20Prototype-orange)

</div>

---

## Overview

An air gap is a security boundary, not a guarantee that a system cannot leak information.

Malware may attempt to encode information into physical signals, including electromagnetic emissions and acoustic patterns.

**AetherHound** is a cybersecurity research prototype designed to explore the detection of these potential covert channels through two primary monitoring systems:

- **RF Monitoring:** Captures radio-frequency signals using supported RTL-SDR hardware and analyzes their spectral behavior.
- **Acoustic Monitoring:** Captures microphone input and analyzes frequency characteristics, signal bursts, and modulation patterns.

AetherHound integrates signal acquisition, digital signal processing (DSP), statistical anomaly detection, synthetic simulation, and a local web dashboard into one platform.

It also includes a software-only fan-pattern simulator that generates Morse-like acoustic signals for controlled testing.

> AetherHound is a defensive research prototype. Detected anomalies are indicators for investigation, not proof of malware or successful data exfiltration.

## Key Features

| Module | Features |
|---|---|
| RF Acquisition | RTL-SDR device discovery and IQ sample capture |
| RF Analysis | FFT, Power Spectrum, Noise Floor Estimation |
| RF Detection | Statistical anomaly detection and persistence filtering |
| Acoustic Acquisition | Microphone discovery and audio recording |
| Acoustic Analysis | RMS Energy, Spectral Centroid, Frequency Analysis |
| Morse Detection | Streaming pulse detection and SOS recognition |
| Simulation | Synthetic RF and acoustic signal generation |
| Fan Simulator | Virtual RPM trajectories and Morse-code audio |
| Backend | Python API and real-time detection integration |
| Dashboard | React-based monitoring interface |
| Evidence | Capture metadata and SHA-256 hashes |

## System Architecture

```text
                    AETHERHOUND
                         |
             +-----------+-----------+
             |                       |
         RF PIPELINE            ACOUSTIC PIPELINE
             |                       |
      RTL-SDR / IQ INPUT       MICROPHONE INPUT
             |                       |
        FFT / PSD             DIGITAL FILTERING
             |                       |
      RF ANOMALY             ACOUSTIC FEATURE
       DETECTOR                 EXTRACTION
             |                       |
             |                 MORSE DETECTOR
             |                       |
             +-----------+-----------+
                         |
                   REALTIME ENGINE
                         |
                    PYTHON API
                         |
                   REACT DASHBOARD
                         |
                EVENTS / LOGS / PLOTS

              SYNTHETIC TEST ENGINE
                         |
                SOFTWARE SIMULATION
```

### RF Monitoring Workflow

1. Acquire complex IQ samples from a supported RTL-SDR receiver.
2. Process sample windows using FFT-based spectral analysis.
3. Estimate the local noise floor and signal variation.
4. Identify spectral peaks exceeding configured thresholds.
5. Apply persistence checks and hysteresis to reduce false alerts.

### Acoustic Monitoring Workflow

1. Acquire audio samples through a configured microphone.
2. Apply digital filtering.
3. Extract RMS energy and spectral characteristics.
4. Detect amplitude bursts and periodic modulation.
5. Identify pulse durations and compare patterns against the target Morse sequence.

### Simulation Workflow

AetherHound includes a software-only simulation environment that generates synthetic RF and acoustic signals. This allows the detection pipeline to be tested without physical SDR or microphone hardware.

Synthetic events are explicitly identified as simulated data.

## Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python 3.11+ |
| Signal Processing | NumPy, SciPy |
| RF Acquisition | RTL-SDR, PyRTLSDR |
| Audio Acquisition | PyAudio, PortAudio |
| Audio Processing | SoundDevice, SoundFile |
| Backend | Python API |
| Frontend | React |
| Frontend Tooling | Vite, npm |
| Testing | Pytest |
| Visualization | Matplotlib |

## Repository Structure

```text
Infotact-Project-1/
│
├── aetherhound/
│   ├── api/
│   ├── hardware/
│   ├── detection/
│   ├── mock_malware/
│   ├── scripts/
│   └── tests/
│
├── data/
│   ├── rf/
│   ├── acoustic/
│   ├── mock_fan/
│   ├── events/
│   └── plots/
│
├── public/
├── scripts/
├── src/
│
├── .env.example
├── .gitignore
├── index.html
├── metadata.json
├── package.json
├── package-lock.json
├── requirements.txt
├── tsconfig.json
└── vite.config.ts
```

## Requirements

### Software Requirements

- Python 3.11 or later
- Node.js and npm
- Git
- Windows 10/11 or Linux
- VS Code (recommended)

### Optional Hardware Requirements

| Hardware | Purpose |
|---|---|
| RTL-SDR v3/v4 | RF Signal Reception |
| RF Antenna | RF Signal Reception |
| USB Microphone | Acoustic Signal Capture |
| Raspberry Pi 4/5 | Embedded Processing |
| Linux PC | Signal Processing |
| Speaker | Optional Acoustic Testing |

**Note:** The current RF acquisition backend supports RTL-SDR through PyRTLSDR and librtlsdr. HackRF is not supported by this backend.

## Installation & Setup

### 1. Clone Repository

```bash
git clone https://github.com/preet-bhavsar/Infotact-Project-1.git
cd Infotact-Project-1
```

If you are using the `Preet-Bhavsar` branch:

```bash
git fetch origin
git switch Preet-Bhavsar
```

### 2. Python Environment Setup

**Windows PowerShell**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Linux**

```bash
sudo apt-get update

sudo apt-get install -y \
rtl-sdr \
librtlsdr-dev \
libusb-1.0-0-dev \
portaudio19-dev

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Frontend Dependencies

```bash
npm install
```

### 4. RTL-SDR Setup on Windows

1. Connect the RTL-SDR device.
2. Open Zadig.
3. Select Options → List All Devices.
4. Select Bulk-In, Interface (Interface 0).
5. Install the WinUSB driver.

Verify installation:

```powershell
pip install pyrtlsdr
python -c "import rtlsdr; print('RTL-SDR Ready')"
```

## Configuration

AetherHound supports environment-based configuration.

Example configuration:

```ini
AETHERHOUND_RF_CENTER_FREQ_HZ=433920000
AETHERHOUND_RF_SAMPLE_RATE_HZ=2048000
AETHERHOUND_RF_GAIN=auto

AETHERHOUND_AUDIO_DEVICE_INDEX=1
AETHERHOUND_AUDIO_SAMPLE_RATE_HZ=44100
AETHERHOUND_AUDIO_CHANNELS=1
```

| Variable | Description |
|---|---|
| AETHERHOUND_RF_CENTER_FREQ_HZ | RF Center Frequency |
| AETHERHOUND_RF_SAMPLE_RATE_HZ | RF Sample Rate |
| AETHERHOUND_RF_GAIN | RTL-SDR Gain |
| AETHERHOUND_AUDIO_DEVICE_INDEX | Microphone Device Index |
| AETHERHOUND_AUDIO_SAMPLE_RATE_HZ | Audio Sample Rate |
| AETHERHOUND_AUDIO_CHANNELS | Audio Channels |
| AETHERHOUND_AUDIO_CHUNK_SIZE | Audio Chunk Size |

Use the microphone device index reported by your system.

## Running AetherHound

Run Python commands from the project root with the virtual environment activated.

### 1. Software-Only Demonstration

No physical hardware is required.

```bash
python -m aetherhound.scripts.week1_demo --mode software --duration 8
```

This workflow:

- Generates synthetic RF IQ samples.
- Generates synthetic acoustic samples.
- Injects a simulated narrowband RF anomaly.
- Executes the processing and detection pipeline.
- Logs detection events.
- Exports visualization plots.

Synthetic results are not real-world RF or acoustic captures.

### 2. RTL-SDR Device Discovery

```bash
python -m aetherhound.hardware.rf_capture list
```

Configure RF parameters.

**PowerShell**

```powershell
$env:AETHERHOUND_RF_CENTER_FREQ_HZ = "433920000"
$env:AETHERHOUND_RF_SAMPLE_RATE_HZ = "2048000"
$env:AETHERHOUND_RF_GAIN = "auto"
```

**Linux**

```bash
export AETHERHOUND_RF_CENTER_FREQ_HZ=433920000
export AETHERHOUND_RF_SAMPLE_RATE_HZ=2048000
export AETHERHOUND_RF_GAIN=auto
```

Capture RF samples:

```bash
python -m aetherhound.hardware.rf_capture capture --duration 2 --output-dir data/rf/raw
```

Successful captures generate:

- Complex IQ samples (`.npy`)
- FFT spectrum data (`.spectrum.npz`)
- JSON capture metadata
- SHA-256 artifact hashes

### 3. Microphone Discovery & Recording

List available microphones:

```bash
python -m aetherhound.hardware.acoustic_capture list
```

Record audio:

```bash
python -m aetherhound.hardware.acoustic_capture record --device-index 1 --duration 5 --sample-rate 44100 --channels 1 --output-dir data/acoustic/raw
```

Recording metadata includes microphone information, capture timestamp, sample rate, duration, RMS energy, peak amplitude, zero-crossing rate, and SHA-256 hash.

### 4. Fan Morse-Code Simulator

Generate synthetic SOS fan patterns:

```bash
python -m aetherhound.mock_malware.fan_pattern_simulator --message SOS --output-dir data/mock_fan
```

Generate a custom message:

```bash
python -m aetherhound.mock_malware.fan_pattern_simulator --message "HELLO WORLD" --dot-duration 0.15 --dash-duration 0.45 --sample-rate 44100
```

The simulator generates virtual RPM trajectories, Morse pulse timelines, synthetic WAV audio, JSON simulation metadata, and detection results.

**Safety:** This simulator is entirely software-based. It does not access or modify physical fans, motherboard controls, thermal settings, or firmware.

### 5. Start the Backend API

Open the first terminal:

```bash
python -m aetherhound.api
```

### 6. Start the React Dashboard

Open a second terminal:

```bash
npm run dev
```

Open the local dashboard:

```text
http://localhost:3000
```

The dashboard provides monitoring controls to start acquisition, pause monitoring, resume monitoring, stop monitoring, view detection events, and monitor available sensor status.

The API does not silently substitute synthetic acquisition when physical hardware is unavailable.

## Detection Methodology

### 1. RF Statistical Anomaly Detection

The RF detector performs:

- Windowed FFT analysis.
- Power spectrum calculation.
- Median noise-floor estimation.
- Median Absolute Deviation (MAD).
- Spectral peak detection.
- Persistence filtering.
- Hysteresis-based alert stabilization.

Noise floor:

\[
NoiseFloor = median(P_{dB})
\]

Noise variation:

\[
\sigma_{noise} =
1.4826 \times median(
|P_{dB} - NoiseFloor|
)
\]

The prototype identifies peaks exceeding approximately 4.5 standard deviations from the estimated noise floor. Peaks must persist across at least three consecutive windows to reduce transient false positives.

### 2. Acoustic Signal Analysis

The acoustic processor uses:

- Butterworth Bandpass Filtering
- RMS Energy Extraction
- Spectral Centroid Calculation
- Dominant Frequency Tracking
- Amplitude Burst Detection
- Streaming Envelope Extraction

The documented processing band is 50 Hz–8,000 Hz.

### 3. Morse Pattern Detection

The streaming Morse detector:

1. Extracts the signal envelope.
2. Tracks dynamic range using rolling percentiles.
3. Uses an adaptive Schmitt trigger.
4. Segments short and long pulses.
5. Classifies dots and dashes.
6. Searches for the SOS sequence.

Target Morse sequence:

```text
... --- ...
```

Documented match score:

\[
MatchScore =
0.70 \times (1.0 - MeanTimingError)
+
0.30 \times Fidelity
\]

These parameters describe the prototype implementation and require validation against representative real-world recordings.

## Data & Generated Outputs

```text
data/
│
├── rf/
│   ├── raw/
│   ├── processed/
│   └── metadata/
│
├── acoustic/
│   ├── raw/
│   ├── processed/
│   └── metadata/
│
├── mock_fan/
│   ├── audio/
│   ├── rpm/
│   └── metadata/
│
├── events/
│   ├── rf_events.jsonl
│   ├── acoustic_events.jsonl
│   ├── morse_events.jsonl
│   └── system_events.jsonl
│
└── plots/
    ├── rf_spectrum/
    ├── rf_waterfall/
    ├── acoustic_waveform/
    └── acoustic_spectrogram/
```

Generated files depend on the workflows executed.

## Testing & Validation

Run Python tests:

```bash
python -m pytest aetherhound/tests -q
```

Compile-check the Python package:

```bash
python -m compileall -q aetherhound
```

Frontend lint:

```bash
npm run lint
```

Frontend production build:

```bash
npm run build
```

Physical hardware workflows must be validated using the actual supported devices and drivers. Passing software tests does not prove physical RF or acoustic acquisition.

## Troubleshooting

| Problem | Solution |
|---|---|
| RTL-SDR not detected | Verify USB connection and driver installation |
| `usb_open error -3` | Check Linux DVB-T kernel driver conflicts |
| `librtlsdr` error | Verify librtlsdr installation |
| Microphone unavailable | Check permissions and device index |
| PyAudio installation failure | Install PortAudio dependencies |
| ALSA Unknown PCM | Check audio device configuration |
| Dropped audio chunks | Increase chunk size or reduce sample rate |
| HackRF not supported | Current backend requires RTL-SDR |

## Hardware Limitations

- RTL-SDR has limited instantaneous bandwidth.
- Wider RF monitoring may require frequency stepping.
- Standard microphones may not capture ultrasonic signals.
- Ultrasonic monitoring requires suitable sensors and compatible high sample rates.
- Synthetic testing does not establish physical covert-channel activity.
- RF and acoustic anomalies may have benign causes.

## Security & Responsible Use

AetherHound is intended for authorized cybersecurity research, defensive security monitoring, controlled laboratory experiments, and academic research.

Users must:

- Monitor only authorized systems and environments.
- Follow applicable RF and recording regulations.
- Treat anomalies as investigation indicators.
- Preserve the distinction between physical and synthetic data.
- Never interfere with physical cooling or safety systems.

## Project Status

**Current Phase: Week 1 – Research Prototype**

Implemented project areas include:

- RF acquisition workflow
- Acoustic acquisition workflow
- Signal processing and detection components
- Synthetic RF and acoustic testing
- Fan Morse-code simulation
- Local Python API integration
- React monitoring dashboard

Physical acquisition requires compatible hardware, drivers, and a suitable test environment.

## Contributing

Contributions and suggestions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Implement your changes.
4. Add or update relevant tests.
5. Run Python and frontend checks.
6. Submit a pull request with a clear description.

## License

No license has currently been specified. Unless a LICENSE file is added, standard copyright applies and reuse permissions are not automatically granted.

---

<div align="center">

# AETHERHOUND

### Visibility Beyond the Network.

**Monitor. Detect. Investigate.**

Built for Cybersecurity Research & Defensive Experimentation.

</div>
