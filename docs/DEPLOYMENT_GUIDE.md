# AetherHound: Air-Gapped Deployment & Operations Guide

**Document ID:** AH-DOC-DEP-004  
**Author:** Bharanidharan D (Security Admin Associate L1. Intern)  
**Classification:** Operational Guide - Infotact Solutions  

---

## 1. Deployment Requirements

AetherHound is built strictly for **air-gapped and hyper-local environments**:
- **Zero Cloud Connectivity:** No telemetry, DNS, HTTP, or outbound API requests.
- **No Web Frameworks:** No Node.js, Express, React, or browser engines. All monitoring runs on native Curses/Rich TTY consoles.
- **Minimal Dependencies:** Standard Python 3.10+ with NumPy, SciPy, PyTorch CPU, and Rich.

---

## 2. Step-by-Step Installation

### Step 1: Clone Repository & Create Virtual Environment
```bash
git clone https://github.com/Infotact-Solutions/AetherHound.git
cd AetherHound
python -m venv venv

# On Linux/Raspberry Pi:
source venv/bin/activate

# On Windows:
.\venv\Scripts\Activate.ps1
```

### Step 2: Install Python Dependencies
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Step 3: Run Model Training & Baseline Calibration
```bash
python train_model.py
```
This trains the Autoencoder on baseline server hum, computes ROC curves, and exports `evaluation_results/autoencoder_best.pt`.

### Step 4: Verify Full Pipeline via Test Suite
```bash
python -m pytest tests/ -v
```
All 16 unit and integration tests must pass.

---

## 3. Running AetherHound

### 3.1 Interactive Hacker Terminal (Console Mode)
```bash
python run_demo.py --interactive
```
Launches the full dark-mode Rich tactical terminal UI displaying:
- Live 2D ASCII Spectrum Waterfall
- Server room spatial rack map with pinpointed infected rack
- Real-time MSE reconstruction error and adaptive threshold
- Peak frequency and SNR telemetry
- Demodulated covert channel plaintext payload

### 3.2 Headless Audit Mode (Automated Logging)
```bash
python run_demo.py
```
Runs a 20-frame audit demonstration and logs structured incident records into `logs/aetherhound_incidents.jsonl`.

### 3.3 Running Mock Malware in a Controlled Sandbox
To generate test acoustic covert pulses safely:
```bash
python -m aetherhound.malware.fansmitter --message "FLAG{TEST_1337}"
```

To run capture validation for Mid-Project Review:
```bash
python -m aetherhound.malware.exfil_test_runner
```

---

## 4. Raspberry Pi Systemd Service Setup

To run AetherHound continuously upon edge hardware boot:

Create `/etc/systemd/system/aetherhound.service`:
```ini
[Unit]
Description=AetherHound Air-Gapped Covert Channel Detection Appliance
After=sound.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/AetherHound
ExecStart=/home/pi/AetherHound/venv/bin/python run_demo.py --interactive
Restart=always
RestartSec=5
StandardOutput=journal+console

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable aetherhound.service
sudo systemctl start aetherhound.service
```
