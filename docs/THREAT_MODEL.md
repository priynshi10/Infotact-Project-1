# AetherHound: Threat Model & Physical Attack Taxonomy

**Document ID:** AH-DOC-THR-005  
**Author:** Bharanidharan D (Security Admin Associate L1. Intern)  
**Classification:** Security Assessment - Infotact Solutions  

---

## 1. Threat Landscape: Air-Gapped Exfiltration

In air-gapped environments, attackers bridge physical isolation through malware planted via compromised supply chains, infected maintenance USB drives (e.g., Stuxnet), or insider access. Once resident on target hosts, malware cannot establish outbound TCP/IP connections.

Adversaries instead leverage **unintentional physical emissions (TEMPEST / side-channel emanations)** to transmit data to an external receiver (e.g., compromised smartphone, SDR antenna outside the facility, or rogue microphone planted in the facility).

```
[Air-Gapped Host] ---> [PWM/Bus Modulation] ---> [Air-Gap Physical Medium] ---> [Attacker Receiver]
(Infected Server)       (Fan / RAM / Actuator)     (Acoustic / EM Waves)         (Spy Mic / SDR)
```

---

## 2. Attack Vectors & Taxonomy

### 2.1 Acoustic Channels (Fansmitter & DiskFiltration)
- **Fansmitter (Guri et al., 2016):** Malware modulates the rotational velocity of internal chassis/CPU cooling fans. By adjusting fan PWM duty cycle or scheduling CPU-intensive compute bursts, the acoustic tone emitted by fan blade rotation shifts between distinct frequencies (Frequency-Shift Keying - FSK) or pulses on/off (On-Off Keying - OOK / Morse code). Bitrates range from 1 to 15 bits per minute across distances of 1 to 8 meters.
- **DiskFiltration (Guri et al., 2016):** Malware controls the physical movement of mechanical hard drive actuator arms during seek operations, emitting acoustic chirp patterns.

### 2.2 Electromagnetic & RF Channels (RAMBO & AirHopper)
- **RAMBO (Guri et al., 2018):** Malware executes fast memory read/write operations (e.g., non-temporal AVX streaming instructions) across multiple RAM memory channels. The high-speed switching of data and address lines on the DDR bus generates electromagnetic radiation in the HF/VHF radio spectrum (typically 24 MHz to 100 MHz).
- **AirHopper (Guri et al., 2014):** Malware modulates GPU display cable signals to emit FM-radio signals decodable by standard mobile FM receivers.

---

## 3. Threat Model Matrix (STRIDE & MITRE ATT&CK)

| Threat ID | MITRE ATT&CK | Vector | Threat Description | AetherHound Countermeasure |
| :--- | :--- | :--- | :--- | :--- |
| **TH-01** | **T1041** (Exfiltration Over C2) | Fansmitter (Acoustic) | Exfiltrating AES keys via CPU fan PWM acoustic tones | Continuous STFT + Autoencoder anomaly detection flagging abnormal harmonic energy |
| **TH-02** | **T1092** (Communication Through Removable Media) | USBee / RAMBO (RF) | Radiating memory bus bursts to SDR receiver outside wall | SDR receiver scanning 24.5 MHz + spectral kurtosis detector |
| **TH-03** | **T1001** (Data Obfuscation) | Morse / Spread Spectrum | Low-SNR exfiltration hidden beneath ambient server hum | 4-element microphone array with spatial beamforming + Welch PSD |
| **TH-04** | **T1562** (Impair Defenses) | Acoustic jamming / Noise injection | Adversary generating loud noise to mask covert signals | Adaptive statistical thresholding ($\mu + 2.5\sigma$) with robust normalization |

---

## 4. Defense-in-Depth Mitigation Recommendations

In addition to deploying AetherHound:
1. **Fan Speed Clamping:** Lock motherboard BIOS/UEFI fan speed profiles to constant RPM curves to eliminate PWM frequency variance.
2. **RF Shielding (Faraday Cages):** Install copper-mesh Faraday shielding around server racks to attenuate RF emanations by 40+ dB.
3. **Acoustic Baffles & Mufflers:** Install acoustic absorption panels in server plenum chambers.
4. **Physical Inspection:** Restrict unauthorized radio receivers, recording devices, and mobile phones within 30 meters of air-gapped zones.
