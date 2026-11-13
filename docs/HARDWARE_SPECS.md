# AetherHound: Hardware Specifications & Sensor Array Design

**Document ID:** AH-DOC-HW-001  
**Author:** Bharanidharan D (Security Admin Associate L1. Intern)  
**Classification:** Confidential - Infotact Solutions  

---

## 1. Hardware Architecture Overview

AetherHound operates as a hyper-local, edge-deployed sensor appliance designed for physical security in air-gapped server facilities. It eliminates standard IT dependencies, cloud APIs, and web servers, operating entirely on isolated embedded compute hardware.

```
                          +------------------------------------------+
                          |   AETHERHOUND EDGE APPLIANCE ENCLOSURE   |
                          |                                          |
[4-Mic Array Array] ----->| USB 3.0 (ALSA Audio 48/96 kHz)           |
                          |                                          |
[HackRF One / SDR]  ----->| USB 3.0 (libusb / IQ 2.4 MSPS)           |
                          |                                          |
[Piezo Alarm Buzzer]<-----| GPIO Pin 18 (PWM Alarm Trigger)          |
                          |                                          |
[Local Curses CLI]  <-----| HDMI / Direct Local TTY Console          |
                          +------------------------------------------+
```

---

## 2. Component Specifications

### 2.1 Core Compute Unit (Edge Appliance)
- **Model:** Industrial Raspberry Pi 5 / Raspberry Pi 4 Model B (or NVIDIA Jetson Orin Nano).
- **Processor:** Broadcom BCM2712 Quad-core ARM Cortex-A76 (64-bit @ 2.4 GHz).
- **Memory:** 8 GB LPDDR4X SDRAM.
- **Storage:** 64 GB Industrial Class-10 MicroSD or NVMe M.2 SSD via PCIe HAT.
- **Cooling:** Passive aluminum heatsink with ultra-quiet fluid dynamic bearing fan (acoustic baseline < 18 dB SPL to avoid self-interference).
- **Power:** 5V / 5A DC USB-C with redundant UPS battery backup.

### 2.2 Acoustic & Ultrasonic Sensor Array
- **Hardware:** Seeed Studio ReSpeaker 4-Mic Circular Array v2.0 (or Knowles Ultrasonic SPM0404UD5).
- **Channels:** 4 independent microphone elements configured in a circular 64 mm radius array.
- **Sensitivity:** -26 dBFS @ 1 kHz, 94 dB SPL.
- **Acoustic Overload Point (AOP):** 120 dB SPL.
- **Frequency Response:** 100 Hz to 24 kHz (standard mode) and up to 48 kHz (ultrasonic mode @ 96 kHz Fs).
- **Signal-to-Noise Ratio (SNR):** 64 dBA.
- **ADC:** XMOS XVF3000 Voice Processor with 24-bit delta-sigma converters.

### 2.3 Software Defined Radio (SDR)
- **Primary Radio:** Great Scott Gadgets HackRF One.
  - Frequency Range: 1 MHz to 6 GHz.
  - Bandwidth: 20 MHz maximum (typically configured for 2.4 MSPS to 10 MSPS).
  - ADC Resolution: 8 bits.
  - Sample Rate: 2 MSPS to 20 MSPS (standard mode configured @ 2.4 MSPS).
  - Interface: USB 2.0 High Speed.
- **Secondary / Low-Cost Alternative:** RTL-SDR Blog V4 (R828D tuner with HF direct sampling).
  - Frequency Range: 500 kHz to 1.75 GHz.
  - Bandwidth: 2.4 MHz stable.
  - Built-in Bias-T and TCXO (0.5 PPM temperature compensated).

### 2.4 Physical Alerting Peripheral
- **Buzzer:** 5V Active Piezoelectric Sounder (85 dB @ 10 cm, 2.3 kHz).
- **GPIO Pinout:**
  - `Pin 18 (GPIO 24)`: Logic HIGH triggers buzzer alarm pulse.
  - `Pin 6`: Ground (GND).
  - `Pin 2`: 5V VCC Power.

---

## 3. Server Room Geometry & Sensor Coordinates

The system is calibrated for an 8m x 6m standard data center layout with 6 server racks:

| Node ID | Physical Coordinates (X, Y) | Function |
| :--- | :--- | :--- |
| **Sensor-North** | (4.0m, 6.0m) | Ceiling mount north row monitor |
| **Sensor-South** | (4.0m, 0.5m) | Southern ingress boundary monitor |
| **Sensor-East** | (8.0m, 3.5m) | Eastern wall rack monitor |
| **Sensor-West** | (0.5m, 3.5m) | Western perimeter monitor |
| **Rack-Alpha** | (1.0m, 2.0m) | Monitored compute rack 1 |
| **Rack-Beta** | (1.0m, 5.0m) | Monitored compute rack 2 |
| **Rack-Gamma** | (4.0m, 2.0m) | Monitored compute rack 3 |
| **Rack-Delta** | (4.0m, 5.0m) | Monitored compute rack 4 |
| **Rack-Epsilon** | (7.0m, 2.0m) | Monitored compute rack 5 |
| **Rack-Zeta** | (7.0m, 5.0m) | Monitored compute rack 6 |
