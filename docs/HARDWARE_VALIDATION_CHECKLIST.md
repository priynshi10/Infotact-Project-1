# Hardware Validation Checklist

Status: pending physical validation.

## Equipment

- RTL-SDR device with antenna if RF validation is attempted
- Audio input microphone and optional speaker
- Host PC or Raspberry Pi
- Appropriate USB/driver support

## RF checks

1. Connect the RTL-SDR and antenna.
2. Windows: configure the USB driver with Zadig only if required.
3. Linux: install `librtlsdr` and verify the device does not have a DVB-T kernel-driver conflict.
4. Run `python -m aetherhound.hardware.rf_capture list`.
5. Run `python -m aetherhound.hardware.device_check`.
6. Capture a bounded recording with `python -m aetherhound.hardware.rf_capture capture --duration 1`.
7. Verify the metadata source, sample count, hash, center frequency and no synthetic label.

No hardware RF result is valid until these commands execute with an actual device.

Native GNU Radio remains pending in this environment. It can only be reported as initialized after `gnuradio.gr.top_block` instantiation succeeds in a compatible environment.

### GNU Radio setup path (unverified on this Windows machine)

Recommended approach: use a dedicated Conda environment, because GNU Radio native binaries and Python bindings are distributed by the OS/package ecosystem rather than reliably through ordinary `pip`.

```powershell
conda create -n aetherhound-gnuradio -c conda-forge python=3.11 gnuradio
conda activate aetherhound-gnuradio
python -c "import gnuradio; print('GNU Radio installed')"
python -m aetherhound.scripts.capability_check
```

This setup path was not executed here. Do not assume Windows Conda package availability for every GNU Radio release.

## Virtual SDR validation

Run:

```powershell
python -m aetherhound.scripts.virtual_sdr_demo --backend python --seconds 5
python -m aetherhound.scripts.system_monitor --seconds 1
python -m aetherhound.scripts.arm64_compat
```

Virtual IQ playback:

```powershell
python -c "import numpy as np; t=np.arange(16384)/2048000.; np.save('data/rf/raw/virtual_iq.npy',(0.5*np.exp(2j*np.pi*150000*t)).astype(np.complex64))"
python -m aetherhound.scripts.virtual_sdr_demo --input-npy data/rf/raw/virtual_iq.npy --seconds 2
```

## Raspberry Pi deployment

Target: Raspberry Pi OS 64-bit, ARM64/aarch64, Python 3.11-compatible environment, at least NumPy, SciPy, Rich and optional PyTorch. Install dependencies in `/opt/aetherhound/.venv`.

Copy the deployment unit to `/etc/systemd/system/aetherhound.service`, start with `sudo systemctl enable --now aetherhound.service`, and stop with `sudo systemctl stop aetherhound.service`.

This repository has not performed Raspberry Pi or ARM64 emulation testing in the current Windows environment.

## Acoustic checks

1. Connect and enumerate a microphone.
2. Run `python -m aetherhound.hardware.acoustic_capture list`.
3. Record: `python -m aetherhound.hardware.acoustic_capture record --duration 5`.
4. For physical speaker-loopback, obtain explicit confirmation and keep playback volume low.
5. Verify WAV metadata, source label and cryptographic hash.

## GNU Radio

Run `python -m aetherhound.scripts.capability_check`. If GNU Radio is unavailable, the documented fallback is active. Native validation requires an installed, importable GNU Radio API and a tested flowgraph on the target machine.
