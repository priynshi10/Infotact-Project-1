#!/usr/bin/env python3
"""
AetherHound Evidence & Data Provenance Integrity Verifier
Audits all generated signal plots against raw acquisition buffers and cryptographic metadata.
Ensures zero unverified, static, or orphaned charts exist in the intelligence pipeline.
"""

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import glob
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

import numpy as np
import soundfile as sf

# Try importing Rich for high-visibility terminal output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


@dataclass
class PlotAuditResult:
    plot_name: str
    plot_path: str
    metadata_found: bool
    metadata_path: Optional[str]
    source_mode: str
    sensor_id: str
    capture_timestamp_iso: str
    sample_rate_hz: float
    sample_count_recorded: int
    raw_data_path: str
    raw_data_exists: bool
    raw_data_type: str
    hash_verified: bool
    recorded_sha256: str
    computed_sha256: str
    samples_verified: bool
    actual_samples: int
    timestamp_verified: bool
    audit_status: str  # PASS_HARDWARE, PASS_SIMULATION, FAIL_CORRUPTED, FAIL_ORPHAN
    failure_reasons: List[str]


def compute_file_sha256(file_path: str) -> str:
    """Compute SHA-256 hash of an existing file on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_array_sha256(arr: np.ndarray) -> str:
    """Compute deterministic SHA-256 hash of a NumPy array buffer."""
    return hashlib.sha256(arr.tobytes()).hexdigest()


def verify_plot_evidence(plot_path: str, base_dir: str) -> PlotAuditResult:
    """Audit an individual plot file against its raw buffer and metadata."""
    plot_name = os.path.basename(plot_path)
    failures: List[str] = []

    # 1. Locate provenance metadata JSON (adjacent or in channel metadata dir)
    json_path = os.path.splitext(plot_path)[0] + ".json"
    if not os.path.exists(json_path):
        # Look in data/{channel}/metadata/
        parts = plot_path.replace("\\", "/").split("/")
        if "plots" in parts:
            idx = parts.index("plots")
            if idx + 1 < len(parts):
                category = parts[idx + 1]
                channel = "rf" if "rf" in category else ("acoustic" if "acoustic" in category else "mock_fan")
                alt_json = os.path.join(base_dir, "data", channel, "metadata", os.path.splitext(plot_name)[0] + ".json")
                if os.path.exists(alt_json):
                    json_path = alt_json

    if not os.path.exists(json_path):
        return PlotAuditResult(
            plot_name=plot_name,
            plot_path=plot_path,
            metadata_found=False,
            metadata_path=None,
            source_mode="UNKNOWN",
            sensor_id="UNTRACED",
            capture_timestamp_iso="UNKNOWN",
            sample_rate_hz=0.0,
            sample_count_recorded=0,
            raw_data_path="",
            raw_data_exists=False,
            raw_data_type="NONE",
            hash_verified=False,
            recorded_sha256="",
            computed_sha256="",
            samples_verified=False,
            actual_samples=0,
            timestamp_verified=False,
            audit_status="FAIL_ORPHAN",
            failure_reasons=["No cryptographic metadata JSON found for this plot. Traceability broken."],
        )

    # 2. Parse metadata JSON
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception as e:
        return PlotAuditResult(
            plot_name=plot_name,
            plot_path=plot_path,
            metadata_found=True,
            metadata_path=json_path,
            source_mode="CORRUPTED",
            sensor_id="CORRUPTED",
            capture_timestamp_iso="CORRUPTED",
            sample_rate_hz=0.0,
            sample_count_recorded=0,
            raw_data_path="",
            raw_data_exists=False,
            raw_data_type="INVALID",
            hash_verified=False,
            recorded_sha256="",
            computed_sha256="",
            samples_verified=False,
            actual_samples=0,
            timestamp_verified=False,
            audit_status="FAIL_CORRUPTED",
            failure_reasons=[f"Invalid metadata JSON syntax: {e}"],
        )

    source_mode = meta.get("source_mode", "UNKNOWN")
    sensor_id = meta.get("sensor_id", "UNKNOWN")
    t_iso = meta.get("capture_timestamp_iso", "")
    t_epoch = meta.get("capture_timestamp_epoch", 0.0)
    sr_hz = float(meta.get("sample_rate_hz", 0.0))
    rec_samples = int(meta.get("sample_count", 0))
    rec_hash = meta.get("raw_data_sha256", "")
    raw_path = meta.get("raw_data_path", "")

    # Ensure raw path resolves properly whether relative or absolute
    if raw_path and not os.path.isabs(raw_path) and not os.path.exists(raw_path):
        alt_raw = os.path.join(base_dir, raw_path)
        if os.path.exists(alt_raw):
            raw_path = alt_raw

    raw_exists = os.path.exists(raw_path) if raw_path else False
    if not raw_exists:
        failures.append(f"Referenced raw data file not found on disk: {raw_path}")

    # 3. Verify Raw Data Integrity & Hash
    computed_hash = ""
    hash_verified = False
    actual_samples = 0
    samples_verified = False
    raw_type = "UNKNOWN"

    if raw_exists:
        raw_ext = os.path.splitext(raw_path)[1].lower()
        if raw_ext == ".npy":
            raw_type = "NUMPY_ARRAY"
            try:
                arr = np.load(raw_path)
                actual_samples = len(arr)
                # Compute hash of raw bytes
                arr_hash = compute_array_sha256(arr)
                file_hash = compute_file_sha256(raw_path)
                # Match either array memory buffer hash or container file hash
                if rec_hash in (arr_hash, file_hash):
                    hash_verified = True
                    computed_hash = rec_hash
                else:
                    computed_hash = arr_hash
                    failures.append(f"SHA-256 hash mismatch! Recorded: {rec_hash[:16]}..., Computed: {arr_hash[:16]}...")
                samples_verified = (actual_samples == rec_samples)
                if not samples_verified:
                    failures.append(f"Sample count mismatch! Recorded: {rec_samples}, In Array: {actual_samples}")
            except Exception as e:
                failures.append(f"Failed to read raw .npy buffer: {e}")

        elif raw_ext in (".wav", ".wave"):
            raw_type = "AUDIO_WAV"
            try:
                file_hash = compute_file_sha256(raw_path)
                computed_hash = file_hash
                hash_verified = (file_hash == rec_hash)
                if not hash_verified:
                    failures.append(f"SHA-256 hash mismatch! Recorded: {rec_hash[:16]}..., Computed: {file_hash[:16]}...")

                info = sf.info(raw_path)
                actual_samples = info.frames
                samples_verified = (actual_samples == rec_samples)
                if not samples_verified:
                    failures.append(f"Sample count mismatch! Recorded: {rec_samples}, In WAV: {actual_samples}")
            except Exception as e:
                failures.append(f"Failed to inspect raw audio WAV: {e}")

        elif raw_ext in (".csv", ".json", ".txt"):
            raw_type = "TIMELINE_CSV"
            try:
                file_hash = compute_file_sha256(raw_path)
                computed_hash = file_hash
                hash_verified = (file_hash == rec_hash)
                if not hash_verified:
                    failures.append(f"SHA-256 hash mismatch! Recorded: {rec_hash[:16]}..., Computed: {file_hash[:16]}...")

                with open(raw_path, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip()]
                # Exclude header
                actual_samples = max(0, len(lines) - 1)
                samples_verified = (actual_samples == rec_samples)
                if not samples_verified:
                    failures.append(f"Line count mismatch! Recorded: {rec_samples}, In CSV: {actual_samples}")
            except Exception as e:
                failures.append(f"Failed to read CSV timeline: {e}")

    # 4. Verify Timestamps
    timestamp_verified = False
    if t_epoch > 0 or t_iso:
        try:
            # Check ISO 8601 formatting
            if t_iso.endswith("Z"):
                datetime.fromisoformat(t_iso.replace("Z", "+00:00"))
            else:
                datetime.fromisoformat(t_iso)
            timestamp_verified = True
        except Exception:
            failures.append(f"Malformed ISO timestamp string: {t_iso}")

    # 5. Determine Overall Audit Status
    if failures:
        audit_status = "FAIL_INTEGRITY"
    elif source_mode == "LIVE HARDWARE":
        audit_status = "PASS_HARDWARE"
    elif source_mode == "SYNTHETIC SIMULATION":
        audit_status = "PASS_SIMULATION"
    elif source_mode == "RECORDED HARDWARE DATA":
        audit_status = "PASS_RECORDED"
    else:
        audit_status = "UNKNOWN_SOURCE"
        failures.append(f"Unrecognized source_mode: {source_mode}")

    return PlotAuditResult(
        plot_name=plot_name,
        plot_path=plot_path,
        metadata_found=True,
        metadata_path=json_path,
        source_mode=source_mode,
        sensor_id=sensor_id,
        capture_timestamp_iso=t_iso,
        sample_rate_hz=sr_hz,
        sample_count_recorded=rec_samples,
        raw_data_path=raw_path,
        raw_data_exists=raw_exists,
        raw_data_type=raw_type,
        hash_verified=hash_verified,
        recorded_sha256=rec_hash,
        computed_sha256=computed_hash,
        samples_verified=samples_verified,
        actual_samples=actual_samples,
        timestamp_verified=timestamp_verified,
        audit_status=audit_status,
        failure_reasons=failures,
    )


def run_full_audit(base_dir: str) -> Dict[str, Any]:
    """Execute complete provenance audit across all plot directories."""
    plot_patterns = [
        os.path.join(base_dir, "data", "plots", "**", "*.png"),
        os.path.join(base_dir, "aetherhound", "data", "plots", "**", "*.png"),
    ]

    plot_files = []
    for pattern in plot_patterns:
        plot_files.extend(glob.glob(pattern, recursive=True))

    # Deduplicate plot paths
    plot_files = sorted(list(set(os.path.abspath(p) for p in plot_files)))

    results: List[PlotAuditResult] = []
    for p in plot_files:
        res = verify_plot_evidence(p, base_dir)
        results.append(res)

    pass_count = sum(1 for r in results if r.audit_status.startswith("PASS"))
    hardware_count = sum(1 for r in results if r.audit_status == "PASS_HARDWARE")
    sim_count = sum(1 for r in results if r.audit_status == "PASS_SIMULATION")
    recorded_count = sum(1 for r in results if r.audit_status == "PASS_RECORDED")
    fail_count = sum(1 for r in results if not r.audit_status.startswith("PASS"))

    audit_summary = {
        "audit_timestamp_iso": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "audit_timestamp_epoch": time.time(),
        "total_plots_audited": len(results),
        "total_passed": pass_count,
        "hardware_derived_count": hardware_count,
        "synthetic_simulation_count": sim_count,
        "recorded_hardware_count": recorded_count,
        "failed_or_orphaned_count": fail_count,
        "audit_passed": (fail_count == 0 and len(results) > 0),
        "plots": [asdict(r) for r in results],
    }

    # Save report to data/evidence_audit_report.json and public/data/evidence_audit_report.json
    out_paths = [
        os.path.join(base_dir, "data", "evidence_audit_report.json"),
        os.path.join(base_dir, "public", "data", "evidence_audit_report.json"),
        os.path.join(base_dir, "aetherhound", "data", "evidence_audit_report.json"),
    ]
    for outp in out_paths:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(outp)), exist_ok=True)
            with open(outp, "w", encoding="utf-8") as f:
                json.dump(audit_summary, f, indent=2)
        except Exception as e:
            print(f"[!] Warning: Could not write report to {outp}: {e}")

    return audit_summary


def print_audit_report(summary: Dict[str, Any]) -> None:
    """Print high-contrast, professional CLI report."""
    total = summary["total_plots_audited"]
    passed = summary["total_passed"]
    failed = summary["failed_or_orphaned_count"]
    hw = summary["hardware_derived_count"]
    sim = summary["synthetic_simulation_count"]

    if RICH_AVAILABLE:
        console = Console()
        console.print()
        console.print(
            Panel.fit(
                f"[bold cyan]AETHERHOUND SIGNAL EVIDENCE AUTHENTICITY AUDIT[/bold cyan]\n"
                f"[bold white]Timestamp:[/bold white] {summary['audit_timestamp_iso']} | "
                f"[bold white]Status:[/bold white] "
                f"{'[bold green]VERIFIED AUTHENTIC[/bold green]' if summary['audit_passed'] else '[bold red]AUDIT FAILED[/bold red]'}",
                border_style="cyan",
            )
        )

        table = Table(title="Signal Evidence Verification Summary", show_header=True, header_style="bold magenta")
        table.add_column("Plot Filename", style="dim", width=26)
        table.add_column("Source Mode", justify="center")
        table.add_column("Sensor ID", justify="center")
        table.add_column("Raw Data Binding", justify="left")
        table.add_column("SHA-256 Check", justify="center")
        table.add_column("Sample Count", justify="right")
        table.add_column("Audit Result", justify="center")

        for p in summary["plots"]:
            status_style = (
                "[bold green]PASS (HW)[/bold green]" if p["audit_status"] == "PASS_HARDWARE" else (
                    "[bold yellow]PASS (SIM)[/bold yellow]" if p["audit_status"] == "PASS_SIMULATION" else (
                        "[bold blue]PASS (REC)[/bold blue]" if p["audit_status"] == "PASS_RECORDED" else "[bold red]FAIL[/bold red]"
                    )
                )
            )
            hash_style = "[green]MATCH[/green]" if p["hash_verified"] else "[red]MISMATCH[/red]"
            samples_style = f"{p['actual_samples']:,}" if p["samples_verified"] else f"[red]{p['actual_samples']} != {p['sample_count_recorded']}[/red]"
            raw_short = os.path.basename(p["raw_data_path"]) if p["raw_data_path"] else "[red]None[/red]"

            table.add_row(
                p["plot_name"],
                p["source_mode"],
                p["sensor_id"],
                raw_short,
                hash_style,
                samples_style,
                status_style,
            )

        console.print(table)
        console.print(
            f"\n[bold]Total Plots:[/bold] {total} | "
            f"[bold green]Live Hardware:[/bold green] {hw} | "
            f"[bold yellow]Synthetic Sim:[/bold yellow] {sim} | "
            f"[bold red]Failed/Orphaned:[/bold red] {failed}\n"
        )
    else:
        print("\n" + "=" * 70)
        print("AETHERHOUND SIGNAL EVIDENCE AUTHENTICITY AUDIT")
        print("=" * 70)
        print(f"Timestamp: {summary['audit_timestamp_iso']}")
        print(f"Total Plots Audited: {total}")
        print(f"Passed: {passed} | Hardware: {hw} | Synthetic: {sim} | Failed: {failed}")
        print("-" * 70)
        for p in summary["plots"]:
            status = p["audit_status"]
            print(f"- {p['plot_name']}: [{p['source_mode']}] Sensor: {p['sensor_id']} -> {status}")
            if p["failure_reasons"]:
                for r in p["failure_reasons"]:
                    print(f"    * FAILURE: {r}")
        print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="AetherHound Evidence Authenticity Verifier")
    parser.add_argument("--base-dir", default=".", help="Base project directory")
    args = parser.parse_args()

    base_dir = os.path.abspath(args.base_dir)
    summary = run_full_audit(base_dir)
    print_audit_report(summary)

    if not summary["audit_passed"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
