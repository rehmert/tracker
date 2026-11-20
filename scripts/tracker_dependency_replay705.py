#!/usr/bin/env python3
"""Release 705: two independent, hash-locked, strictly offline /tmp Python replays.

Requires a DEV-only network-isolated systemd worker and exact source SHA.
Never installs into /opt/tracker, downloads wheels/browsers, or touches app data.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import subprocess
import sys

from scripts import tracker_dependency_acquire705 as acquire
from scripts import tracker_dependency_baseline569 as baseline
from scripts import tracker_dependency_lock705 as lock
from scripts import tracker_dependency_readiness705 as readiness

EXPECTED_SOURCE = "release/705-csrf-dependency-closeout"
TEST_MODULES = (
    "tests/test_csrf_all_registered_negative705.py",
    "tests/test_release705_combined.py",
    "tests/test_release627_csrf_reconciliation.py",
    "tests/test_release569_dependency_baseline.py",
)
MAX_CMD_SECONDS = 900


class ReplayError(RuntimeError):
    pass


def assert_network_isolated() -> None:
    # A separate systemd PrivateNetwork namespace is a mandatory, independent
    # guard beyond pip --no-index and a minimal process environment.
    private = os.readlink("/proc/self/ns/net")
    host = os.readlink("/proc/1/ns/net")
    if private == host:
        raise ReplayError("No separate network namespace; require PrivateNetwork=yes")


def private_dir(path: Path, *, prefix: str) -> None:
    if (not path.is_absolute()
            or path.parent != Path("/tmp")
            or not path.name.startswith(prefix)
            or path.is_symlink() or not path.is_dir()
            or path.stat().st_uid != 0
            or path.stat().st_mode & 0o077):
        raise ReplayError("Private /tmp work or evidence directory is unsafe")


def verify_approved_wheels(root: Path) -> tuple[list[dict], dict[str, str]]:
    pins = lock.all_pins()
    if len(pins) != 44 or pins.get("pip") != "25.1.1":
        raise ReplayError("Unexpected Release 569 package baseline")
    # Same root ownership/mode and approved exact pin inventory as acquisition,
    # but here the finalized receipts MUST exist and cannot be overwritten.
    if (not root.is_absolute() or root.parent != Path("/tmp")
            or not re.fullmatch(r"tracker705-wheel-acquire[.][A-Za-z0-9_]{8}", root.name)
            or root.is_symlink() or not root.is_dir()
            or root.stat().st_uid != 0 or root.stat().st_mode & 0o077):
        raise ReplayError("Wheel acquisition root is not an exact private retained root")
    for child in ("wheelhouse", "receipts"):
        path = root / child
        if (path.is_symlink() or not path.is_dir()
                or path.stat().st_uid != 0 or path.stat().st_mode & 0o077):
            raise ReplayError(f"Untrusted {child} directory")
    expected_pins = "".join(f"{name}=={pins[name]}\n" for name in sorted(pins))
    reqs = root / "approved-pins705.txt"
    if (reqs.is_symlink() or not reqs.is_file()
            or reqs.stat().st_uid != 0 or reqs.stat().st_mode & 0o077
            or reqs.read_text(encoding="utf-8") != expected_pins):
        raise ReplayError("Approved original pinned requirements mismatch")

    wheels = root / "wheelhouse"
    receipt_dir = root / "receipts"
    rows = lock.verify(wheels, receipt_dir)["wheels"]
    readiness.wheelhouse_audit(wheels)
    origin = receipt_dir / "pypi-sha256705.json"
    if (origin.is_symlink() or not origin.is_file()
            or origin.stat().st_uid != 0 or origin.stat().st_mode & 0o077):
        raise ReplayError("Private PyPI file receipt missing")
    record = json.loads(origin.read_text(encoding="utf-8"))
    by_name = {row["name"]: row for row in rows}
    claimed = record.get("wheels")
    if (record.get("schema_version") != 1 or not isinstance(claimed, list)
            or len(claimed) != len(rows)):
        raise ReplayError("PyPI SHA256 receipt is incomplete")
    checked = set()
    for item in claimed:
        name = item.get("name")
        if name not in by_name or name in checked:
            raise ReplayError("PyPI SHA256 receipt contains unknown or duplicate wheel")
        checked.add(name)
        row = by_name[name]
        for field in ("name", "version", "filename", "sha256", "bytes"):
            if item.get(field) != row[field]:
                raise ReplayError(f"PyPI SHA256 receipt mismatch for {name}")
        if (item.get("pypi_release_api") !=
                f"https://pypi.org/pypi/{name}/{row['version']}/json"
                or item.get("pypi_yanked") is not False
                or not str(item.get("pypi_file_url", "")).startswith(
                    "https://files.pythonhosted.org/")):
            raise ReplayError(f"Untrusted PyPI receipt origin for {name}")
    print("DEPENDENCY_705_OFFLINE_WHEEL_SHA256=VERIFIED_44", flush=True)
    print("DEPENDENCY_705_OFFLINE_WHEEL_PROVENANCE=RECORDED_PYPI_NOT_INDEPENDENT", flush=True)
    return rows, pins


def sandbox_env(home: Path, data: Path, temp: Path, source: Path) -> dict[str, str]:
    return {
        "HOME": str(home),
        "TMPDIR": str(temp),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(source),
        "TRACKER_DATA_DIR": str(data),
        "TRACKER_INSTANCE": "DEV",
        "PIP_CONFIG_FILE": os.devnull,
        "PIP_NO_INDEX": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PIP_NO_CACHE_DIR": "1",
    }


def offline_install_args(python: Path, wheelhouse: Path, hashed: Path) -> list[str]:
    return [
        str(python), "-B", "-m", "pip", "--isolated", "install",
        "--disable-pip-version-check", "--no-input",
        "--no-index", "--no-cache-dir", "--only-binary=:all:",
        "--require-hashes", "--find-links", str(wheelhouse),
        "--requirement", str(hashed),
    ]


def run_logged(
    command: list[str], logfile: Path, *,
    environment: dict[str, str], cwd: Path, timeout: int = MAX_CMD_SECONDS,
) -> None:
    # Retain every command's stdout/stderr without leaking environment values.
    if logfile.exists() or logfile.is_symlink():
        raise ReplayError("Refuse to overwrite an existing replay log")
    with logfile.open("x", encoding="utf-8") as output:
        os.chmod(logfile, 0o600)
        result = subprocess.run(
            command, cwd=cwd, env=environment, stdout=output,
            stderr=subprocess.STDOUT, check=False, timeout=timeout,
        )
    if result.returncode:
        tail = logfile.read_text(encoding="utf-8", errors="replace").splitlines()[-45:]
        print(f"DEPENDENCY_705_FAILED_LOG={logfile}", flush=True)
        for line in tail:
            print(line, flush=True)
        raise ReplayError(f"Isolated command exited {result.returncode}: {logfile.name}")


def replay_pass(
    number: int, source: Path, runroot: Path, evidence: Path,
    wheelhouse: Path, requirements: Path, base_python: Path,
) -> dict:
    name = f"pass{number}"
    venv = runroot / f"{name}-venv"
    home, data, temp = (runroot / f"{name}-{part}"
                        for part in ("home", "data", "tmp"))
    for path in (home, data, temp):
        path.mkdir(mode=0o700)
    env = sandbox_env(home, data, temp, source)
    print(f"DEPENDENCY_705_REPLAY_{number}=STARTED_CLEAN_VENV", flush=True)
    run_logged(
        [str(base_python), "-B", "-m", "venv", str(venv)],
        evidence / f"{name}-venv.log", environment=env,
        cwd=runroot, timeout=180,
    )
    cfg = (venv / "pyvenv.cfg").read_text(encoding="utf-8").lower()
    if "include-system-site-packages = false" not in cfg:
        raise ReplayError("Disposable virtualenv inherits system packages")
    python = venv / "bin/python"
    # Venv binaries normally symlink to the SAME base Python executable.
    # Reject missing/out-of-sandbox interpreters, not symlink equality.
    if not python.is_file() or not python.is_relative_to(runroot):
        raise ReplayError("Fresh Python interpreter unavailable or unsafe")
    env["PATH"] = f"{venv / 'bin'}:/usr/local/bin:/usr/bin:/bin"

    run_logged(
        offline_install_args(python, wheelhouse, requirements),
        evidence / f"{name}-install.log", environment=env, cwd=source, timeout=600,
    )
    print(f"DEPENDENCY_705_REPLAY_{number}_OFFLINE_INSTALL=PASSED", flush=True)
    manifest = source / "docs/dependencies/observed-2026-11-11-py313.json"
    constraints = source / "docs/dependencies/candidate-constraints-py313.txt"
    run_logged(
        [str(python), "-B", str(source / "scripts/tracker_dependency_baseline569.py"),
         "--instance", "DEV", "--baseline", str(manifest),
         "--constraints", str(constraints)],
        evidence / f"{name}-baseline.log", environment=env, cwd=source, timeout=90,
    )
    print(f"DEPENDENCY_705_REPLAY_{number}_EXACT_44_BASELINE=PASSED", flush=True)
    run_logged(
        [str(python), "-B", "-m", "pip", "--isolated", "check"],
        evidence / f"{name}-pip-check.log", environment=env, cwd=source, timeout=90,
    )
    print(f"DEPENDENCY_705_REPLAY_{number}_PIP_CHECK=PASSED", flush=True)
    run_logged(
        [str(python), "-B", "-m", "pytest", "-q", "--tb=short", "--maxfail=1",
         *TEST_MODULES],
        evidence / f"{name}-backend.log", environment=env, cwd=source, timeout=700,
    )
    print(f"DEPENDENCY_705_REPLAY_{number}_BACKEND=PASSED", flush=True)
    return {"pass": number, "venv_isolated": True, "offline": True,
            "baseline_package_count": 44, "pip_check": True,
            "backend_modules": list(TEST_MODULES)}


def execute(source: Path, sha: str, wheels_root: Path,
            runroot: Path, evidence: Path, base_python: Path) -> None:
    if os.geteuid() != 0 or socket.gethostname().split(".", 1)[0] != "tracker-dev":
        raise ReplayError("Replay limited to root on tracker-dev")
    assert_network_isolated()
    private_dir(runroot, prefix="tracker705-replay-work.")
    private_dir(evidence, prefix="tracker705-replay-evidence.")
    if (source.is_symlink() or not source.is_dir()
            or not source.resolve().is_relative_to(runroot)
            or not re.fullmatch(r"[0-9a-f]{40}", sha)):
        raise ReplayError("Untrusted source worktree or commit argument")
    if (platform.python_version() != "3.13.5"
            or platform.system() != "Linux" or platform.machine() != "x86_64"):
        raise ReplayError("Unexpected Python/platform for approved wheels")
    if (not base_python.is_file() or base_python != Path("/opt/tracker/.venv/bin/python")):
        raise ReplayError("Original DEV interpreter path changed")
    if shutil.disk_usage("/tmp").free < 1024**3:
        raise ReplayError("Under 1 GiB free before independent replay")
    rows, pins = verify_approved_wheels(wheels_root)
    print("DEPENDENCY_705_NETWORK=ISOLATED_PRIVATE_NAMESPACE", flush=True)
    print(f"DEPENDENCY_705_REPLAY_CANDIDATE={sha}", flush=True)
    print(f"DEPENDENCY_705_REPLAY_WHEEL_COUNT={len(rows)}", flush=True)
    print(f"DEPENDENCY_705_REPLAY_EVIDENCE_DIR={evidence}", flush=True)
    passes = []
    for number in (1, 2):
        passes.append(replay_pass(
            number, source, runroot, evidence, wheels_root / "wheelhouse",
            wheels_root / "receipts" / lock.REQUIREMENTS_NAME, base_python,
        ))
        # Detect wheel replacement or mutation between separate installs.
        lock.verify(wheels_root / "wheelhouse", wheels_root / "receipts")
    report = {
        "schema_version": 1, "source_commit": sha,
        "python": platform.python_version(), "platform": platform.platform(),
        "wheel_manifest_sha256": lock.digest(wheels_root / "receipts" / lock.LOCK_NAME),
        "replayed_at_utc": datetime.now(timezone.utc).isoformat(),
        "network": "isolated namespace; pip --no-index; no wheel downloads",
        "results": passes,
        "scope": "Two Python/backend replays only; no Chromium, OS or rollback proof",
    }
    out = evidence / "replay705.json"
    with out.open("x", encoding="utf-8") as f:
        os.chmod(out, 0o600)
        json.dump(report, f, indent=2, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    print("DEPENDENCY_705_TWO_OFFLINE_REPLAYS=PASSED", flush=True)
    print("DEPENDENCY_705_INSTALLED_DEV=UNMODIFIED", flush=True)
    print("DEPENDENCY_705_CHROMIUM_REPLAY=NOT_EXECUTED", flush=True)
    print("DEPENDENCY_705_OS_ROLLBACK=NOT_EXECUTED", flush=True)
    print("DEPENDENCY_705_ISSUE10=BLOCKED_BROWSER_OS_ROLLBACK", flush=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-disposable", action="store_true")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--sha")
    parser.add_argument("--wheel-root", type=Path)
    parser.add_argument("--runroot", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--base-python", type=Path)
    args = parser.parse_args(argv)
    if not args.execute_disposable:
        print("DEPENDENCY_705_OFFLINE_REPLAY=DRY_RUN_ONLY_EXPLICIT_OPT_IN_REQUIRED")
        return 0
    if any(value is None for value in (
        args.source, args.sha, args.wheel_root, args.runroot,
        args.evidence, args.base_python,
    )):
        parser.error("Explicit SHA, worktree, wheel root, isolated roots and Python required")
    try:
        execute(args.source, args.sha, args.wheel_root,
                args.runroot, args.evidence, args.base_python)
        return 0
    except (OSError, ValueError, subprocess.SubprocessError, ReplayError) as exc:
        print(f"DEPENDENCY_705_OFFLINE_REPLAY=FAILED ({type(exc).__name__}: {exc})",
              file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
