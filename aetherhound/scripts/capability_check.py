"""Plain, non-hardware capability report for CLI and CI."""

from importlib.util import find_spec
import importlib
import argparse
import platform
import sys


def capability_report() -> dict:
    report = {
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "dsp_backend": "gnu_radio" if find_spec("gnuradio") else "python",
    }
    for name in ("numpy", "scipy", "torch", "tensorflow", "gnuradio", "rtlsdr", "pyaudio", "soundfile", "rich"):
        spec = find_spec(name)
        report[name] = bool(spec)
        if spec:
            try:
                module = importlib.import_module(name)
                report[f"{name}_version"] = str(getattr(module, "__version__", "installed"))
            except Exception:
                report[f"{name}_version"] = "installed"
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="AetherHound dependency capability check")
    args = parser.parse_args()
    report = capability_report()
    print(f"os: {report['os']}")
    print(f"python: {report['python']}")
    print(f"dsp_backend: {report['dsp_backend']}")
    for name in ("numpy", "scipy", "torch", "tensorflow", "gnuradio", "rtlsdr", "pyaudio", "soundfile", "rich"):
        status = "AVAILABLE" if report[name] else "UNAVAILABLE"
        version = report.get(f"{name}_version", "")
        print(f"{name}: {status}" + (f" ({version})" if version else ""))
    if not report["gnuradio"]:
        print("native GNU Radio unavailable; Python DSP fallback active; install/configure GNU Radio to enable native flowgraph")


if __name__ == "__main__":
    main()
