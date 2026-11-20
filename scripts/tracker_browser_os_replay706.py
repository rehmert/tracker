#!/usr/bin/env python3
"""Release 706: isolated Chromium/OS fingerprint + two fresh Python/browser
replays + disposable dependency rollback rehearsal.

Requires systemd PrivateNetwork=yes. Does not install into /opt/tracker,
fetch browsers, access installed Tracker DB, mutate PROD, or claim an
independently rebuilt operating system or supply-chain attestation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import subprocess
import sys

from scripts import tracker_dependency_lock705 as lock
from scripts import tracker_dependency_replay705 as replay

WHEEL_ROOT_RE = re.compile(r"tracker705-wheel-acquire[.][A-Za-z0-9_]{8}\Z")
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")


class EvidenceError(RuntimeError):
    pass


def sha(path: Path) -> str:
    return lock.digest(path)


def safe_binary(path: Path) -> Path:
    resolved = path.resolve(strict=True)
    roots = (Path("/root/.cache/ms-playwright"), Path("/opt/tracker"))
    if (not resolved.is_file() or not os.access(resolved, os.X_OK)
            or resolved.stat().st_uid != 0
            or resolved.stat().st_mode & 0o022
            or not any(resolved.is_relative_to(root) for root in roots)):
        raise EvidenceError("Chromium executable is not trusted installed/cache binary")
    return resolved


def shared_libraries(binary: Path) -> dict[str, dict[str, str]]:
    result = subprocess.run(
        ["/usr/bin/ldd", str(binary)],
        capture_output=True, text=True, check=False, timeout=45,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
    )
    if result.returncode or "not found" in result.stdout + result.stderr:
        raise EvidenceError("Chromium requires missing or unreadable OS libraries")
    linked = {}
    for line in result.stdout.splitlines():
        value = None
        match = re.search(r"^\s*(\S+)\s+=>\s+(/\S+)\s+\(", line)
        if match:
            key, value = match.group(1), match.group(2)
        else:
            match = re.search(r"^\s*(/\S+)\s+\(", line)
            if match:
                value = match.group(1)
                key = Path(value).name
        if value is None:
            continue
        path = Path(value).resolve(strict=True)
        if not path.is_file() or path.stat().st_uid != 0:
            raise EvidenceError("A required system shared library is untrusted")
        if key in linked:
            raise EvidenceError("Duplicate OS library dependency")
        linked[key] = {"resolved": str(path), "sha256": sha(path)}
    if len(linked) < 5:
        raise EvidenceError("No meaningful shared-library inventory found")
    return dict(sorted(linked.items()))


def browser_smoke(*, output: Path, executable: Path | None) -> dict:
    replay.assert_network_isolated()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        binary = safe_binary(executable or Path(pw.chromium.executable_path))
        browser = pw.chromium.launch(
            executable_path=str(binary),
            headless=True,
            timeout=30000,
        )
        try:
            page = browser.new_page()
            response = page.goto(
                "data:text/html,%3Ctitle%3ETracker%20706%20offline%3C/title%3E"
                "%3Ch1%20id%3Dproof%3Eoffline-ready%3C/h1%3E",
                wait_until="load",
            )
            if (page.title() != "Tracker 706 offline"
                    or page.locator("#proof").inner_text() != "offline-ready"):
                raise EvidenceError("Chromium local-page smoke failed")
            version = browser.version
        finally:
            browser.close()
    os_release = Path("/etc/os-release")
    if not os_release.is_file():
        raise EvidenceError("OS release inventory unavailable")
    report = {
        "schema_version": 1,
        "scope": "local binary launch under an isolated network namespace; same host OS",
        "chromium_executable": str(binary),
        "chromium_sha256": sha(binary),
        "chromium_version": version,
        "os_release_sha256": sha(os_release),
        "libc": platform.libc_ver(),
        "kernel": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "shared_libraries": shared_libraries(binary),
        "url_scope": "data:text/html only",
        "network": "private namespace",
        "browser_download": False,
    }
    if output.exists() or output.is_symlink() or output.parent.stat().st_mode & 0o077:
        raise EvidenceError("Browser evidence destination must be fresh and private")
    with output.open("x", encoding="utf-8") as stream:
        os.chmod(output, 0o600)
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(f"DEPENDENCY_706_BROWSER_SHA256={report['chromium_sha256']}", flush=True)
    print(f"DEPENDENCY_706_BROWSER_LIBRARIES={len(report['shared_libraries'])}", flush=True)
    print("DEPENDENCY_706_CHROMIUM_LOCAL_OFFLINE=PASSED", flush=True)
    return report


def compare_browser(left: dict, right: dict) -> None:
    for field in (
        "chromium_executable", "chromium_sha256", "chromium_version",
        "os_release_sha256", "libc", "kernel", "machine", "shared_libraries",
    ):
        if left.get(field) != right.get(field):
            raise EvidenceError(f"Chromium/host library reproducibility differs: {field}")
    if left.get("url_scope") != right.get("url_scope"):
        raise EvidenceError("Browser smoke scope mismatch")


def report_read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def base_environment(source: Path, home: Path, data: Path, temp: Path) -> dict[str, str]:
    env = replay.sandbox_env(home, data, temp, source)
    # The subprocess receives no caller environment/credentials. This is used
    # for installed and fresh venv browser launch, with explicit binary path.
    return env


def call_browser(
    python: Path, source: Path, evidence: Path, logfile: Path,
    output: Path, executable: Path | None, home: Path, data: Path, temp: Path,
) -> dict:
    env = base_environment(source, home, data, temp)
    env["PATH"] = f"{python.parent}:/usr/local/bin:/usr/bin:/bin"
    args = [
        str(python), "-B", str(source / "scripts/tracker_browser_os_replay706.py"),
        "--browser-smoke", "--out", str(output),
    ]
    if executable is not None:
        args += ["--browser-executable", str(executable)]
    replay.run_logged(args, logfile, environment=env, cwd=source, timeout=120)
    return report_read(output)


def rollback_rehearsal(
    source: Path, runroot: Path, evidence: Path, wheels: Path, baseline: dict,
) -> None:
    # Deliberately corrupt ONLY one fresh disposable virtual environment.
    # The immutable local wheelhouse and installed /opt/tracker/.venv stay untouched.
    venv = runroot / "pass1-venv"
    snapshot = runroot / "pass1-rollback-snapshot"
    if not (venv / "pyvenv.cfg").is_file() or snapshot.exists():
        raise EvidenceError("Fresh venv not present for rollback rehearsal")
    shutil.copytree(venv, snapshot, symlinks=True)
    home = runroot / "pass1-home"
    data = runroot / "pass1-data"
    temp = runroot / "pass1-tmp"
    environment = base_environment(source, home, data, temp)
    environment["PATH"] = f"{venv / 'bin'}:/usr/local/bin:/usr/bin:/bin"
    python = venv / "bin/python"
    replay.run_logged(
        [str(python), "-B", "-m", "pip", "--isolated", "uninstall",
         "--yes", "packaging"],
        evidence / "rollback-remove-package.log",
        environment=environment, cwd=source, timeout=90,
    )
    replay.run_logged(
        [str(python), "-B", "-c",
         "import importlib.metadata as m; assert 'packaging' not in "
         "{d.metadata['Name'].lower() for d in m.distributions()}"],
        evidence / "rollback-drift-observed.log",
        environment=environment, cwd=source, timeout=60,
    )
    print("DEPENDENCY_706_DISPOSABLE_DRIFT=VERIFIED", flush=True)

    shutil.rmtree(venv)
    shutil.copytree(snapshot, venv, symlinks=True)
    replay.run_logged(
        [str(python), "-B", "-m", "pip", "--isolated", "check"],
        evidence / "rollback-pip-check.log",
        environment=environment, cwd=source, timeout=60,
    )
    replay.run_logged(
        [str(python), "-B", str(source / "scripts/tracker_dependency_baseline569.py"),
         "--instance", "DEV",
         "--baseline", str(source / "docs/dependencies/observed-2026-11-11-py313.json"),
         "--constraints", str(source / "docs/dependencies/candidate-constraints-py313.txt")],
        evidence / "rollback-baseline.log",
        environment=environment, cwd=source, timeout=90,
    )
    result = call_browser(
        python, source, evidence, evidence / "rollback-browser.log",
        evidence / "rollback-browser.json",
        Path(baseline["chromium_executable"]), home, data, temp,
    )
    compare_browser(baseline, result)
    lock.verify(wheels / "wheelhouse", wheels / "receipts")
    print("DEPENDENCY_706_DISPOSABLE_ROLLBACK=PASSED", flush=True)


def execute(source: Path, sha_commit: str, wheels: Path,
            runroot: Path, evidence: Path, base_python: Path) -> None:
    if os.geteuid() != 0 or socket.gethostname().split(".", 1)[0] != "tracker-dev":
        raise EvidenceError("DEV root only")
    replay.assert_network_isolated()
    replay.private_dir(runroot, prefix="tracker706-browser-work.")
    replay.private_dir(evidence, prefix="tracker706-browser-evidence.")
    if (not SHA_RE.fullmatch(sha_commit) or not source.is_dir()
            or not source.resolve().is_relative_to(runroot)
            or base_python != Path("/opt/tracker/.venv/bin/python")):
        raise EvidenceError("Unexpected exact-source or installed Python path")
    if shutil.disk_usage("/tmp").free < 1024**3:
        raise EvidenceError("Insufficient scratch space for browser replay")
    rows, _pins = replay.verify_approved_wheels(wheels)
    home, data, temp = (runroot / f"host-{part}" for part in ("home", "data", "tmp"))
    for entry in (home, data, temp):
        entry.mkdir(mode=0o700)
    baseline = call_browser(
        base_python, source, evidence, evidence / "host-browser.log",
        evidence / "host-browser.json", None, Path("/root"), data, temp,
    )
    print("DEPENDENCY_706_HOST_BROWSER_OS_INVENTORY=VERIFIED", flush=True)

    reports = []
    for number in (1, 2):
        replay.replay_pass(
            number, source, runroot, evidence, wheels / "wheelhouse",
            wheels / "receipts" / lock.REQUIREMENTS_NAME, base_python,
        )
        venv_python = runroot / f"pass{number}-venv/bin/python"
        report = call_browser(
            venv_python, source, evidence, evidence / f"pass{number}-browser.log",
            evidence / f"pass{number}-browser.json",
            Path(baseline["chromium_executable"]),
            runroot / f"pass{number}-home",
            runroot / f"pass{number}-data",
            runroot / f"pass{number}-tmp",
        )
        compare_browser(baseline, report)
        lock.verify(wheels / "wheelhouse", wheels / "receipts")
        print(f"DEPENDENCY_706_OFFLINE_CHROMIUM_PASS_{number}=PASSED", flush=True)
        reports.append(report)

    rollback_rehearsal(source, runroot, evidence, wheels, baseline)
    report = {
        "schema_version": 1,
        "source_commit": sha_commit,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "wheel_sha256_manifest": sha(wheels / "receipts" / lock.LOCK_NAME),
        "browser_sha256": baseline["chromium_sha256"],
        "browser_version": baseline["chromium_version"],
        "library_count": len(baseline["shared_libraries"]),
        "independent_fresh_python_browser_passes": len(reports),
        "disposable_dependency_rollback": "passed",
        "limitations": [
            "Chromium originally installed on this host; its upstream origin is not independently attested",
            "Both replays use the same existing host OS libraries; not an independently rebuilt OS",
            "Rollback is an isolated disposable Python environment, not a live DEV/PROD rollback",
            "Advisory/vulnerability review and separately sourced OS/browser provenance remain pending",
            "No global CSRF activation or route-closure claim",
        ],
    }
    outfile = evidence / "issue10-browser-replay706.json"
    with outfile.open("x", encoding="utf-8") as stream:
        os.chmod(outfile, 0o600)
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print("DEPENDENCY_706_BROWSER_OS_LOCAL_REPRO=PASSED_SAME_HOST", flush=True)
    print("DEPENDENCY_706_ISSUE10=STILL_BLOCKED_INDEPENDENT_PROVENANCE_AND_LIVE_ROLLBACK", flush=True)
    print("DEPENDENCY_706_INSTALLED_ENV=UNMODIFIED", flush=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute-disposable", action="store_true")
    mode.add_argument("--browser-smoke", action="store_true")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--sha")
    parser.add_argument("--wheel-root", type=Path)
    parser.add_argument("--runroot", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--base-python", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--browser-executable", type=Path)
    args = parser.parse_args(argv)
    if not args.execute_disposable and not args.browser_smoke:
        print("DEPENDENCY_706=NO_ACTION_EXPLICIT_MODE_REQUIRED")
        return 0
    try:
        if args.browser_smoke:
            if args.out is None:
                raise EvidenceError("--out is required for browser smoke")
            browser_smoke(output=args.out, executable=args.browser_executable)
        else:
            if any(item is None for item in (
                args.source, args.sha, args.wheel_root, args.runroot,
                args.evidence, args.base_python,
            )):
                raise EvidenceError("Exact source, wheel, runroot and evidence required")
            execute(args.source, args.sha, args.wheel_root, args.runroot,
                    args.evidence, args.base_python)
        return 0
    except (EvidenceError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"DEPENDENCY_706_RUNTIME=BLOCKED ({type(exc).__name__}: {exc})",
              file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
