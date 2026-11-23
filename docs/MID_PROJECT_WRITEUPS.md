# Infotact Mid-Project Review Weekly Write-Ups (Weeks 1–2)
**Intern:** Bharanidharan D | **ID:** ITS/CS/1193 | **Domain:** Cyber Security
**Project:** AetherHound: Air-Gapped RF & Acoustic Covert Channel Detector
**Branch:** `Bharani`

---

## 1. Week 1 Write-up (09 Nov – 16 Nov · 3 Valid Commits)

### Short Update (Dashboard Text Box):
During Week 1, I spearheaded the core hardware abstraction and digital signal processing foundation for AetherHound. I engineered real-time sensor ingestion interfaces for dual-channel RTL-SDR complex IQ sampling and PyAudio microphone audio streams. To establish controlled defense validation without physical air-gap tampering, I implemented a high-fidelity server room acoustic and RF physics emulator alongside benign proof-of-concept exfiltration tools (Fansmitter PWM fan modulation encoding Morse "SOS"). On the signal processing pipeline, I developed 4th-order Butterworth bandpass filtering, 50/60 Hz power-line notch rejection, rolling STFT waterfall buffers, and an adaptive Median Absolute Deviation (MAD) noise floor estimator to suppress shifting server room acoustic dynamics.

### Key Deliverables Completed:
- Implemented RTL-SDR and PyAudio non-blocking hardware capture drivers (`aetherhound/sensors/`).
- Built physics-based acoustic and RF server room environment emulator (`emulator.py`).
- Developed benign CPU fan Morse code simulator (`fansmitter.py`) generating aerodynamic sidebands.
- Deployed Butterworth bandpass and 50/60Hz notch rejection filters in `dsp/filters.py`.
- Formulated rolling Median Absolute Deviation (MAD) noise floor tracking (`detector_dsp.py`).
- Validated initial unit test suite verifying sensor streaming and filter isolation.

### Commit Summary (3 Commits):
1. `463c7b3` (13 Nov 2026): `feat: implement AetherHound air-gapped RF & acoustic covert channel detection platform`
2. `c782cef` (14 Nov 2026): `perf(dsp): optimize rolling waterfall buffer and FFT window overlap for sub-10ms latency`
3. `81785ed` (15 Nov 2026): `feat(detector): add adaptive noise floor estimation using rolling Median Absolute Deviation (MAD)`

---

## 2. Week 2 Write-up (16 Nov – 23 Nov · 7 Valid Commits)

### Short Update (Dashboard Text Box):
In Week 2, I expanded AetherHound into an end-to-end multi-modal intrusion detection and localization platform. I enhanced our mock covert suite by synthesizing continuous-phase dual-tone FSK signals for RAMBO-RF memory-bus leakage. For physical spatial localization, I designed a multi-sensor 3D Log-Distance Path Loss pinpointer calibrated with Wall Attenuation Factor (WAF) modeling to isolate target server racks despite dense partition reflections. I integrated an unsupervised PyTorch Deep Convolutional Autoencoder (ROC-AUC = 0.9167) fused with classical peak SNR tracking for defense-in-depth anomaly detection. To satisfy air-gap compliance rules, I built a native dark-mode Curses/Rich terminal UI updating at 30+ FPS, authored a comprehensive RTL-SDR gain staging handbook, implemented continuous latency stress tests (<100ms cycle budget), and signed off the 22/22 passing automated test suite for Mid-Project Review.

### Key Deliverables Completed:
- Enhanced RAMBO-RF simulator with dual-tone Frequency-Shift Keying (FSK) modulation (`rambo_rf.py`).
- Calibrated 3D Log-Distance Path Loss rack localization engine with Wall Attenuation Factor (`triangulator.py`).
- Added sample verification datasets: playable acoustic WAV, raw RF IQ array, and RPM timeline CSV (`data/`).
- Built unsupervised PyTorch ConvAutoencoder inference engine with forensic residual heatmap export (`evaluator.py`).
- Engineered multi-modal anomaly fusion combining spectral reconstruction residuals and peak SNR detectors.
- Implemented tactical air-gapped Curses/Rich terminal UI with dynamic 2D ASCII server room grid visualizer.
- Authored standard operating procedures for RTL-SDR gain staging and thermal PPM calibration (`docs/CALIBRATION_GUIDE.md`).
- Executed continuous multi-channel latency stress profiling asserting real-time throughput (`tests/test_stress.py`).
- Prepared formal Mid-Project Review audit checklist and verification sign-off with 22/22 passing automated tests (`docs/MID_PROJECT_REVIEW_CHECKLIST.md`).

### Commit Summary (7 Commits):
1. `da4f39c` (16 Nov 2026): `test(malware): expand RAMBO-RF simulator with Frequency-Shift Keying (FSK) modulation`
2. `32e81e9` (17 Nov 2026): `feat(triangulation): calibrate multi-wall attenuation factors for server rack room obstacles`
3. `0cd3b9f` (18 Nov 2026): `feat(ml): add reconstruction residual heatmap visualizer and multi-modal anomaly fusion`
4. `fe32b0d` (19 Nov 2026): `feat(cli): add 2D ASCII rack server room grid visualizer to tactical terminal`
5. `4ba1743` (20 Nov 2026): `docs(specs): add hardware gain staging and RTL-SDR calibration handbook`
6. `a53db7b` (21 Nov 2026): `test(e2e): add automated multi-channel stress test runner and latency profiling`
7. `d391072` (22 Nov 2026): `chore(mid-review): add Mid-Project Review audit checklist and verification sign-off`
