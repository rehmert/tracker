#!/usr/bin/env python3
"""Release 705: explicitly approved PyPI wheel acquisition, download-only.

This script creates a private /tmp wheelhouse and retained hash receipts.
It never installs packages, alters the installed venv, downloads browsers,
accesses the Tracker DB or approves global CSRF or dependency replay.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import signal
import socket
import subprocess
import sys
import tempfile
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from scripts import tracker_dependency_baseline569 as baseline
from scripts import tracker_dependency_lock705 as lock
from scripts import tracker_dependency_readiness705 as readiness

PYPI_INDEX = "https://pypi.org/simple"
PYPI_API = "https://pypi.org/pypi"
EXPECTED_PYTHON = "3.13.5"
EXPECTED_PINS = 44
MAX_PYPI_JSON_BYTES = 4 * 1024 * 1024
MAX_DOWNLOAD_SECONDS = 1200


class AcquisitionError(RuntimeError):
    pass


def checked_pins() -> dict[str, str]:
    pins = lock.all_pins()
    if (len(pins) != EXPECTED_PINS
            or pins.get("pip") != "25.1.1"
            or platform.python_version() != EXPECTED_PYTHON
            or platform.system() != "Linux"):
        raise AcquisitionError("Current interpreter/pin baseline is not approved")
    for name, version in pins.items():
        if baseline.PIN.fullmatch(f"{name}=={version}") is None:
            raise AcquisitionError("Invalid baseline pin")
    return pins


def pip_download_args(python: str, requirements: Path, wheelhouse: Path) -> list[str]:
    # Pin every package including pip, do not use cache and do not use
    # an unpinned resolver or any build/source distribution.
    return [
        python, "-B", "-m", "pip", "--isolated", "download",
        "--disable-pip-version-check", "--no-cache-dir", "--no-input",
        "--only-binary=:all:", "--no-deps",
        "--index-url", PYPI_INDEX,
        "--timeout", "20", "--retries", "2",
        "--progress-bar", "off",
        "--dest", str(wheelhouse),
        "--requirement", str(requirements),
    ]


def run_pip_download(command: list[str], home: Path) -> None:
    environment = {
        "HOME": str(home),
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        # pip --isolated ignores user settings, but global/site config
        # can still add other indexes. Disable all pip config files.
        "PIP_CONFIG_FILE": os.devnull,
    }
    print("DEPENDENCY_705_DOWNLOAD=STARTED_PYPI_ONLY", flush=True)
    process = subprocess.Popen(
        command, env=environment, cwd=home, start_new_session=True,
    )
    try:
        status = process.wait(timeout=MAX_DOWNLOAD_SECONDS)
    except subprocess.TimeoutExpired as exc:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        raise AcquisitionError("Pinned wheel download timed out") from exc
    if status:
        raise AcquisitionError(f"Pinned wheel download failed: exit {status}")


def pypi_digest_record(row: dict) -> dict:
    name, version = row["name"], row["version"]
    api_url = f"{PYPI_API}/{quote(name, safe='')}/{quote(version, safe='')}/json"
    request = Request(api_url, headers={
        "Accept": "application/json",
        "User-Agent": "tracker-release705-download-only",
    })
    with urlopen(request, timeout=25) as response:
        actual_url = urlsplit(response.geturl())
        if (actual_url.scheme, actual_url.hostname) != ("https", "pypi.org"):
            raise AcquisitionError("PyPI JSON endpoint redirected off the trusted host")
        body = response.read(MAX_PYPI_JSON_BYTES + 1)
    if len(body) > MAX_PYPI_JSON_BYTES:
        raise AcquisitionError("PyPI release metadata exceeds size limit")
    document = json.loads(body)
    info = document.get("info", {})
    if (baseline.canonical(info.get("name", "")) != name
            or info.get("version") != version):
        raise AcquisitionError(f"PyPI release identity mismatch for {name}")
    matches = [item for item in document.get("urls", [])
               if item.get("filename") == row["filename"]
               and item.get("packagetype") == "bdist_wheel"]
    if len(matches) != 1:
        raise AcquisitionError(f"Wheel absent from official PyPI release listing: {name}")
    record = matches[0]
    file_url = urlsplit(record.get("url", ""))
    if (file_url.scheme, file_url.hostname) != ("https", "files.pythonhosted.org"):
        raise AcquisitionError(f"Unexpected PyPI wheel file host for {name}")
    if record.get("yanked") is not False:
        raise AcquisitionError(f"PyPI wheel is yanked or has unknown status: {name}")
    if record.get("digests", {}).get("sha256") != row["sha256"]:
        raise AcquisitionError(f"PyPI SHA256 does not match downloaded wheel: {name}")
    if record.get("size") != row["bytes"]:
        raise AcquisitionError(f"PyPI artifact byte size mismatch: {name}")
    return {
        "name": name, "version": version, "filename": row["filename"],
        "sha256": row["sha256"], "bytes": row["bytes"],
        "pypi_release_api": api_url, "pypi_file_url": record["url"],
        "uploaded_at": record.get("upload_time_iso_8601"),
        "pypi_yanked": False,
    }


def write_private(path: Path, payload: bytes) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())


def validated_retained_root(root: Path, pins: dict[str, str]) -> None:
    # Only reuse a root created by this acquisition flow. Never scan for
    # a "latest" path or accept an arbitrary wheelhouse.
    if (not root.is_absolute()
            or root.parent != Path("/tmp")
            or not re.fullmatch(r"tracker705-wheel-acquire[.][A-Za-z0-9_]{8}", root.name)
            or root.is_symlink() or not root.is_dir()
            or root.stat().st_uid != 0 or root.stat().st_mode & 0o077):
        raise AcquisitionError("Retained acquisition root is unsafe or out of scope")
    for name in ("wheelhouse", "receipts"):
        directory = root / name
        if (directory.is_symlink() or not directory.is_dir()
                or directory.stat().st_uid != 0
                or directory.stat().st_mode & 0o077):
            raise AcquisitionError(f"Retained {name} directory is unsafe")
    requirements = root / "approved-pins705.txt"
    expected = "".join(f"{name}=={pins[name]}\n" for name in sorted(pins))
    if (requirements.is_symlink() or not requirements.is_file()
            or requirements.stat().st_uid != 0
            or requirements.stat().st_mode & 0o077
            or requirements.read_text(encoding="utf-8") != expected):
        raise AcquisitionError("Retained exact-pin inventory disagrees with baseline")
    # Failed acquisitions before final hash lock should leave this directory
    # empty. Never overwrite or silently trust pre-existing evidence receipts.
    if any((root / "receipts").iterdir()):
        raise AcquisitionError("Retained receipts already exist; refuse replacement")


def acquire(*, retained_root: Path | None = None) -> Path:
    if os.geteuid() != 0 or socket.gethostname().split(".", 1)[0] != "tracker-dev":
        raise AcquisitionError("Approved download-only acquisition requires root on tracker-dev")
    pins = checked_pins()
    if retained_root is None:
        root = Path(tempfile.mkdtemp(prefix="tracker705-wheel-acquire.", dir="/tmp"))
        root.chmod(0o700)
        wheels, receipts = root / "wheelhouse", root / "receipts"
        wheels.mkdir(mode=0o700)
        receipts.mkdir(mode=0o700)
        requirements = root / "approved-pins705.txt"
        write_private(requirements, "".join(
            f"{name}=={pins[name]}\n" for name in sorted(pins)
        ).encode("utf-8"))
    else:
        root = retained_root
        validated_retained_root(root, pins)
        wheels, receipts = root / "wheelhouse", root / "receipts"
        requirements = root / "approved-pins705.txt"
    print(f"DEPENDENCY_705_RETAINED_ROOT={root}", flush=True)
    print("DEPENDENCY_705_INSTALLED_VENV=UNTOUCHED", flush=True)
    print("DEPENDENCY_705_INSTALL=NOT_EXECUTED", flush=True)
    print("DEPENDENCY_705_BROWSER_DOWNLOAD=NOT_EXECUTED", flush=True)
    print(f"DEPENDENCY_705_EXPECTED_PINS={len(pins)}", flush=True)

    if retained_root is None:
        command = pip_download_args(sys.executable, requirements, wheels)
        run_pip_download(command, root)
    else:
        print("DEPENDENCY_705_WHEEL_DOWNLOAD=SKIPPED_REUSING_RETAINED_BYTES", flush=True)

    readiness.safe_wheelhouse(wheels)
    rows = lock.inventory(wheels, pins)
    print(f"DEPENDENCY_705_DOWNLOADED_WHEELS={len(rows)}", flush=True)
    readiness.wheelhouse_audit(wheels)
    print("DEPENDENCY_705_WHEEL_ARCHIVES=VERIFIED", flush=True)

    pypi_rows = [pypi_digest_record(row) for row in rows]
    provenance_receipt = {
        "schema_version": 1,
        "source": "PyPI HTTPS release JSON SHA256 listing; not an independent attestation",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "wheels": pypi_rows,
    }
    write_private(receipts / "pypi-sha256705.json",
                  (json.dumps(provenance_receipt, indent=2, sort_keys=True) + "\n").encode())
    print(f"DEPENDENCY_705_PYPI_SHA256_MATCHES={len(pypi_rows)}", flush=True)

    lock.create(wheels, receipts)
    lock.verify(wheels, receipts)
    print("DEPENDENCY_705_HASH_LOCK=VERIFIED", flush=True)
    print("DEPENDENCY_705_PROVENANCE=PYPI_LISTING_MATCH_NOT_INDEPENDENT", flush=True)
    print("DEPENDENCY_705_REPLAY=NOT_EXECUTED", flush=True)
    print("DEPENDENCY_705_ISSUE10=BLOCKED_PENDING_REPLAY_BROWSER_OS_ROLLBACK", flush=True)
    print("DEPENDENCY_705_ACQUISITION=PASSED_DOWNLOAD_ONLY", flush=True)
    return root


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute-download", action="store_true",
                      help="Explicitly acquire 44 pinned wheels from PyPI without installing")
    mode.add_argument("--verify-retained", type=Path,
                      help="Resume validation of exact previous /tmp acquisition root (no wheel download)")
    args = parser.parse_args(argv)
    if not args.execute_download and args.verify_retained is None:
        print("DEPENDENCY_705_DOWNLOAD=NOT_EXECUTED_REQUIRE_EXPLICIT_FLAG")
        return 0
    try:
        acquire(retained_root=args.verify_retained)
        return 0
    except (OSError, ValueError, subprocess.SubprocessError, AcquisitionError) as exc:
        print(f"DEPENDENCY_705_ACQUISITION=FAILED ({type(exc).__name__}: {exc})",
              file=sys.stderr, flush=True)
        print("DEPENDENCY_705_ISSUE10=BLOCKED", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
