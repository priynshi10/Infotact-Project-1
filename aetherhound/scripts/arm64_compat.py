"""Static ARM64/Linux deployment compatibility report."""

import argparse
import importlib.util
import platform


def compatibility_report() -> dict:
    machine = platform.machine().lower()
    return {
        "os": platform.system(),
        "machine": machine,
        "is_linux": platform.system() == "Linux",
        "is_arm64": machine in ("aarch64", "arm64"),
        "python_compatible": platform.python_version_tuple()[0:2] == ("3", "11"),
        "numpy": importlib.util.find_spec("numpy") is not None,
        "scipy": importlib.util.find_spec("scipy") is not None,
        "torch": importlib.util.find_spec("torch") is not None,
        "psutil": importlib.util.find_spec("psutil") is not None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="AetherHound ARM64 compatibility check")
    args = parser.parse_args()
    report = compatibility_report()
    for key, value in report.items():
        print(f"{key}: {value}")
    if not report["is_linux"] or not report["is_arm64"]:
        print("ARM64_RUNTIME_NOT_TESTED: current environment is not ARM64 Linux")


if __name__ == "__main__":
    main()
