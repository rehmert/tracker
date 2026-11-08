#!/usr/bin/env python3
"""Benchmark complete Tracker test runs without modifying release settings."""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time

from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "tracker-test.sh"

OUTPUT_PARENT = Path("/tmp/tracker-backups")

PASS_RE = re.compile(
    r"(?m)^\s*(\d+) passed(?:,| in )"
)


def environment_capacity() -> dict:
    """Record actual cgroup CPU/memory limits, not just host CPU count."""
    resource = {
        "visible_cpus": os.cpu_count(),
        "affinity_cpus": (
            len(os.sched_getaffinity(0))
            if hasattr(os, "sched_getaffinity") else None
        ),
        "cpu_quota_cpus": None,
        "memory_limit_bytes": None,
    }
    # cgroup v2: avoid assuming an LXC sees the host's entire allocation.
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()
        if quota != "max":
            resource["cpu_quota_cpus"] = round(
                int(quota) / int(period), 2
            )
    except (OSError, ValueError, ZeroDivisionError):
        pass
    try:
        memory = Path("/sys/fs/cgroup/memory.max").read_text().strip()
        if memory != "max":
            resource["memory_limit_bytes"] = int(memory)
    except (OSError, ValueError):
        pass
    return resource


def parse_workers(value: str) -> list[int]:
    try:
        workers = [
            int(part.strip())
            for part in value.split(",")
        ]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "workers must be comma-separated integers"
        ) from exc

    if not workers or len(set(workers)) != len(workers):
        raise argparse.ArgumentTypeError(
            "specify unique worker counts (for example: 8,12,16)"
        )

    if len(workers) > 8 or any(n < 1 or n > 32 for n in workers):
        raise argparse.ArgumentTypeError(
            "specify at most eight worker counts between 1 and 32"
        )

    return workers


def recommendation(
    medians: dict[int, float],
    threshold: float = 0.10,
) -> tuple[int, float]:
    # Permit a second-stage benchmark (8,12,16) without rerunning
    # the already-established 1-worker baseline.
    baseline = medians[min(medians)]
    best = min(
        medians,
        key=lambda workers: medians[workers],
    )

    gain = (
        baseline - medians[best]
    ) / baseline

    selected = (
        best if gain >= threshold else 1
    )

    return selected, max(0.0, gain)


def run_one(
    workers: int,
    repeat: int,
    output: Path,
    timeout: int,
) -> dict:
    log = output / (
        f"workers-{workers}-run-{repeat}.log"
    )

    env = os.environ.copy()

    if workers == 1:
        command = [
            "bash", str(RUNNER), "--full"
        ]
    else:
        command = [
            "bash", str(RUNNER), "--parallel-check"
        ]
        env["TRACKER_TEST_WORKERS"] = str(workers)

    print(
        f"=== {workers} worker(s), run {repeat}: {log} ===",
        flush=True,
    )

    start = time.monotonic()

    with log.open("w", encoding="utf-8") as handle:
        try:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                stdout=handle,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
            returncode = completed.returncode
        except subprocess.TimeoutExpired:
            returncode = 124
            handle.write(
                f"\nTIMEOUT after {timeout} seconds\n"
            )

    elapsed = round(
        time.monotonic() - start, 3
    )

    contents = log.read_text(
        encoding="utf-8",
        errors="replace",
    )

    matches = PASS_RE.findall(contents)

    count = (
        int(matches[-1]) if matches else None
    )

    status = (
        "PASS"
        if returncode == 0 and count is not None
        else "FAIL"
    )

    print(
        f"  {status}: {elapsed:.2f}s; "
        f"passed={count}; exit={returncode}",
        flush=True,
    )

    if status != "PASS":
        print(
            "\n".join(contents.splitlines()[-28:]),
            flush=True,
        )

    return {
        "workers": workers,
        "repeat": repeat,
        "elapsed_seconds": elapsed,
        "passed": count,
        "exit_code": returncode,
        "status": status,
        "log": str(log),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--workers",
        type=parse_workers,
        default=[1, 2, 4],
        help=(
            "unique worker counts 1-32; the lowest count is "
            "the comparison baseline (default: 1,2,4)"
        ),
    )

    parser.add_argument(
        "--repeat",
        type=int,
        default=2,
        help="full runs per worker count, 1-5",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=1200,
        help="timeout per run, 60-3600 seconds",
    )

    args = parser.parse_args(argv)

    if (
        not 1 <= args.repeat <= 5
        or not 60 <= args.timeout <= 3600
    ):
        parser.error(
            "repeat must be 1-5 and timeout 60-3600"
        )

    if any(n > 1 for n in args.workers):
        try:
            import xdist  # noqa: F401
        except ImportError:
            parser.error(
                "pytest-xdist is required for "
                "multi-worker benchmarks"
            )

    if not RUNNER.is_file():
        parser.error(
            f"Test runner not found: {RUNNER}"
        )

    OUTPUT_PARENT.mkdir(
        mode=0o700,
        parents=True,
        exist_ok=True,
    )

    output = Path(
        tempfile.mkdtemp(
            prefix="test-benchmark.",
            dir=OUTPUT_PARENT,
        )
    )
    output.chmod(0o700)

    capacity = environment_capacity()
    print(f"BENCHMARK_CAPACITY={json.dumps(capacity, sort_keys=True)}", flush=True)
    quota = capacity["cpu_quota_cpus"]
    if quota is not None and max(args.workers) > quota:
        print(
            f"WARNING: {max(args.workers)} workers exceed "
            f"effective cgroup CPU quota of {quota:g}; "
            "upgrade the DEV LXC CPU allocation before comparing",
            flush=True,
        )

    results = []
    expected_count = None
    failed = False

    # Interleave worker counts to reduce bias from
    # cache warming or changing system load.
    for repeat in range(1, args.repeat + 1):
        for workers in args.workers:
            result = run_one(
                workers, repeat, output, args.timeout
            )
            results.append(result)

            if result["status"] != "PASS":
                failed = True
                break

            if expected_count is None:
                expected_count = result["passed"]
            elif result["passed"] != expected_count:
                failed = True
                print(
                    "ERROR: Test counts differ between runs",
                    flush=True,
                )
                break

        if failed:
            break

    fully_qualified = (
        not failed
        and len(results)
        == args.repeat * len(args.workers)
    )

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = {
        "created_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "commit": commit,
        "workers": args.workers,
        "baseline_workers": min(args.workers),
        "repeat": args.repeat,
        "expected_passed": expected_count,
        "environment_capacity": capacity,
        "runs": results,
        "fully_qualified": fully_qualified,
    }

    if fully_qualified:
        medians = {
            workers: round(
                statistics.median(
                    result["elapsed_seconds"]
                    for result in results
                    if result["workers"] == workers
                ),
                3,
            )
            for workers in args.workers
        }

        selected, gain = recommendation(
            medians
        )

        report.update({
            "median_seconds": {
                str(k): v
                for k, v in medians.items()
            },
            "recommended_workers": selected,
            "best_observed_gain": round(
                gain, 4
            ),
            "recommendation_rule": (
                "A higher worker count must improve runtime at least "
                "10% versus the lowest benchmarked worker count"
            ),
            "deployment_ready": False,
            "qualification_note": (
                "Benchmark is advisory: repeatability, host memory "
                "and the release systemd memory cap need separate "
                "validation before enabling xdist in deployments"
            ),
        })

        print(
            "=== MEDIAN FULL-SUITE TIME ===",
            flush=True,
        )

        for workers in args.workers:
            print(
                f"  {workers} worker(s): "
                f"{medians[workers]:.2f}s",
                flush=True,
            )

        print(
            f"RECOMMENDATION: {selected} worker(s); "
            f"best measured improvement {gain:.1%} "
            f"versus {min(args.workers)} worker(s)",
            flush=True,
        )

        print(
            "Guarded deployment remains serial.",
            flush=True,
        )

    report_path = output / "report.json"

    report_path.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"REPORT: {report_path}",
        flush=True,
    )

    return 0 if fully_qualified else 1


if __name__ == "__main__":
    sys.exit(main())
