"""
AetherHound Hardware Verification Script
Performs low-level hardware interrogation, sample acquisition tests,
and capability verification for RTL-SDR and audio inputs.
"""

from pathlib import Path
import sys
import time

# Ensure project root is in sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from aetherhound.hardware.config import HardwareConfig
from aetherhound.hardware.device_check import run_diagnostics, print_diagnostic_report
from aetherhound.hardware.rf_capture import RFCaptureDevice
from aetherhound.hardware.acoustic_capture import AcousticCaptureDevice


def main():
    print("\n[+] Initializing AetherHound Hardware Verification Routine...")
    config = HardwareConfig()

    # Step 1: Run diagnostics and enumerate
    results = run_diagnostics(config)
    print_diagnostic_report(results, config)

    # Step 2: Test RTL-SDR capture if connected
    if results.sdr_device.connected:
        print("[+] Testing physical RTL-SDR sample acquisition...")
        rf_cap = RFCaptureDevice(config.rf, synthetic_mode=False)
        started = rf_cap.start()
        if started:
            time.sleep(1.0)
            window = rf_cap.get_window(timeout=2.0)
            rf_cap.stop()
            if window is not None:
                print(f"[SUCCESS] RTL-SDR captured {len(window.samples)} complex IQ samples at {window.center_freq_hz / 1e6:.3f} MHz.")
            else:
                print("[WARNING] RTL-SDR stream started but no IQ samples received within timeout.")
        else:
            print("[FAILURE] Could not initialize physical RTL-SDR.")
    else:
        print("[INFO] Physical RTL-SDR is not connected. To test RF processing pipeline, run week1_demo.py --mode software")

    # Step 3: Test Microphone capture if connected
    if results.mic_device.connected:
        print("\n[+] Testing physical Microphone audio stream...")
        mic_cap = AcousticCaptureDevice(config.acoustic, synthetic_mode=False)
        started = mic_cap.start()
        if started:
            time.sleep(1.0)
            chunk = mic_cap.get_chunk(timeout=2.0)
            mic_cap.stop()
            if chunk is not None:
                print(f"[SUCCESS] Microphone captured {len(chunk.samples)} frames at {chunk.sample_rate_hz} Hz.")
            else:
                print("[WARNING] Audio stream started but no frames received within timeout.")
        else:
            print("[FAILURE] Could not initialize microphone audio stream.")
    else:
        print("\n[INFO] Physical Microphone is not connected. To test acoustic processing pipeline, run week1_demo.py --mode software")

    print("\n[+] Hardware verification completed.\n")


if __name__ == "__main__":
    main()
