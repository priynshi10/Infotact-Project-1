"""CPU/memory monitor for headless Raspberry Pi deployments."""

import argparse
import time

try:
    import psutil
except ImportError:
    psutil = None


def read_metrics() -> dict:
    if psutil is None:
        raise RuntimeError("psutil is not installed")
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": psutil.virtual_memory().percent,
        "memory_available_mb": round(psutil.virtual_memory().available / (1024 * 1024), 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="AetherHound resource monitor")
    parser.add_argument("--seconds", type=float, default=1.0)
    args = parser.parse_args()
    try:
        metrics = read_metrics()
    except RuntimeError as exc:
        parser.exit(1, f"{exc}\n")
    print(f"CPU={metrics['cpu_percent']:.1f}% "
          f"Memory={metrics['memory_percent']:.1f}% "
          f"Available={metrics['memory_available_mb']:.1f} MB")
    time.sleep(max(0.0, args.seconds - 0.1))


if __name__ == "__main__":
    main()
