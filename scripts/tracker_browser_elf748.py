#!/usr/bin/env python3
"""Release 748: hash the resolved Chromium ELF library map, without deployments.

This supplies host evidence missing from the explicitly selected library list
in Release 746. It resolves the trusted installed Playwright Chromium binary
with the system loader's read-only ldd inspection, hashes the resolved ELF
objects, and writes a no-clobber private JSON file under /tmp.

It NEVER downloads, installs, replaces, rolls back, or executes Chromium.
The loader's ldd resolution is an observed map, NOT proof of a reproducible
offline browser/OS reconstruction, complete dynamic loading or tested rollback.
Never put host receipts in GitHub.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

from scripts.tracker_browser_provenance743 import snapshot as browser_snapshot, validate as browser_validate
from scripts.tracker_dependency_baseline569 import BASELINE, read_manifest
from scripts.tracker_host_evidence746 import file_digest

MAX_LIBS = 512
MAX_REPORT = 256000
MAX_LDD = 100000
MAX_TOTAL_BYTES = 8 * 1024 ** 3
SONAME = re.compile(r"[A-Za-z0-9._+-]{1,160}\Z")
DYNAMIC = re.compile(r"^\s*([A-Za-z0-9._+-]+)\s+=>\s+(/\S+)\s+\(0x[0-9A-Fa-f]+\)\s*$")
DIRECT = re.compile(r"^\s*(/\S+)\s+\(0x[0-9A-Fa-f]+\)\s*$")
VDSO = re.compile(r"^\s*linux-vdso\.so\.1\s+\(0x[0-9A-Fa-f]+\)\s*$")
SCOPE = "ldd resolved ELF map only; no offline replay, runtime dlopen or rollback"

class HostEvidenceError(ValueError):
    pass


def parse_ldd(output: str) -> dict[str, Path]:
    """Fail closed on unresolved, colliding, or unexplained loader records."""
    if not isinstance(output, str) or not 0 < len(output) <= MAX_LDD:
        raise HostEvidenceError("Invalid loader output length")
    found: dict[str, Path] = {}
    for line in output.splitlines():
        if not line.strip():
            continue
        if VDSO.fullmatch(line):
            continue
        m = DYNAMIC.fullmatch(line)
        if m:
            name, path = m.group(1), Path(m.group(2))
        else:
            m = DIRECT.fullmatch(line)
            if not m:
                raise HostEvidenceError("Unresolved or unexpected shared library")
            path = Path(m.group(1))
            name = path.name
        if not SONAME.fullmatch(name) or name in found or not path.is_absolute():
            raise HostEvidenceError("Untrusted or duplicate shared library identity")
        found[name] = path
        if len(found) > MAX_LIBS:
            raise HostEvidenceError("Too many shared libraries")
    if not found:
        raise HostEvidenceError("No linked libraries resolved")
    return dict(sorted(found.items()))


def resolved_hashes(paths: dict[str, Path]) -> dict[str, dict]:
    if not paths or len(paths) > MAX_LIBS:
        raise HostEvidenceError("Invalid library inventory")
    output = {}
    bytes_total = 0
    for name, source in paths.items():
        if not SONAME.fullmatch(name) or not source.is_absolute():
            raise HostEvidenceError("Invalid library input")
        # Library symlinks are normal (libz.so.1 -> libz.so.1.2.x).
        # Hash the final regular object, not the symlink or its host path.
        file = source.resolve(strict=True)
        if not stat.S_ISREG(file.stat().st_mode) or file.is_symlink():
            raise HostEvidenceError("Resolved library must be regular")
        digest = file_digest(file)
        bytes_total += digest["bytes"]
        if bytes_total > MAX_TOTAL_BYTES:
            raise HostEvidenceError("Excessive resolved library bytes")
        output[name] = digest
    return dict(sorted(output.items()))


def snapshot(chromium: Path, ldd_output: str | None = None) -> dict:
    baseline = read_manifest(BASELINE)
    provenance = browser_snapshot(chromium)
    if (provenance["python"] != baseline["python"]
            or provenance["playwright"] != baseline["packages"]["playwright"]):
        raise HostEvidenceError("Unexpected installed Python/Playwright versions")
    if ldd_output is None:
        if not Path("/usr/bin/ldd").is_file():
            raise HostEvidenceError("System dynamic loader inspector unavailable")
        if not chromium.is_absolute() or chromium.is_symlink():
            raise HostEvidenceError("Trusted absolute Chromium executable required")
        # No shell, no LD_* variables, no browser process, no network.
        observed = subprocess.run(
            ["/usr/bin/ldd", str(chromium)],
            capture_output=True, text=True, check=False,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
            timeout=90,
        )
        if observed.returncode != 0 or observed.stderr.strip():
            raise HostEvidenceError("Chromium library resolution failed")
        ldd_output = observed.stdout
    result = {
        "schema": 1,
        "browser": provenance,
        "libraries": resolved_hashes(parse_ldd(ldd_output)),
        "scope": SCOPE,
    }
    return validate(result)


def validate(receipt: dict) -> dict:
    if not isinstance(receipt, dict) or set(receipt) != {"schema", "browser", "libraries", "scope"}:
        raise HostEvidenceError("Unexpected evidence fields")
    if receipt["schema"] != 1 or receipt["scope"] != SCOPE:
        raise HostEvidenceError("Overclaimed evidence scope")
    browser_validate(receipt["browser"])
    baseline = read_manifest(BASELINE)
    if (receipt["browser"]["python"] != baseline["python"]
            or receipt["browser"]["playwright"] != baseline["packages"]["playwright"]):
        raise HostEvidenceError("Installed runtime not pinned")
    libs = receipt["libraries"]
    if not isinstance(libs, dict) or not 1 <= len(libs) <= MAX_LIBS:
        raise HostEvidenceError("Invalid library count")
    total = 0
    for name, item in libs.items():
        if not isinstance(name, str) or not SONAME.fullmatch(name):
            raise HostEvidenceError("Invalid library identity")
        if not isinstance(item, dict) or set(item) != {"sha256", "bytes"}:
            raise HostEvidenceError("Invalid library shape")
        if not isinstance(item["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise HostEvidenceError("Invalid library digest")
        if type(item["bytes"]) is not int or not 1 <= item["bytes"] <= 4 * 1024**3:
            raise HostEvidenceError("Invalid library length")
        total += item["bytes"]
        if total > MAX_TOTAL_BYTES:
            raise HostEvidenceError("Library data exceeds bounds")
    return receipt


def private_write(output: Path, receipt: dict) -> None:
    parent = output.parent
    if (not output.is_absolute() or parent.is_symlink() or not parent.is_dir()
            or not parent.resolve().is_relative_to(Path("/tmp"))
            or parent.stat().st_mode & 0o077):
        raise HostEvidenceError("Private /tmp evidence directory required")
    data = (json.dumps(validate(receipt), indent=2, sort_keys=True) + "\n").encode()
    if len(data) > MAX_REPORT:
        raise HostEvidenceError("Evidence exceeds bounded receipt size")
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def private_read(path: Path) -> dict:
    if (path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077
            or not 1 <= path.stat().st_size <= MAX_REPORT):
        raise HostEvidenceError("Private evidence file missing or unsafe")
    return validate(json.loads(path.read_text(encoding="utf-8")))


def compare(dev: dict, prod: dict) -> dict:
    validate(dev)
    validate(prod)
    names = set(dev["libraries"]) | set(prod["libraries"])
    different = sum(dev["libraries"].get(name) != prod["libraries"].get(name) for name in names)
    equal = different == 0 and dev["browser"] == prod["browser"]
    return {
        "schema": 1,
        "matching_host_fingerprints": equal,
        "dev_library_count": len(dev["libraries"]),
        "prod_library_count": len(prod["libraries"]),
        "differing_library_count": different,
        "python_wheel_replay_performed": False,
        "offline_browser_replay_performed": False,
        "full_dynamic_elf_closure_certified": False,
        "os_chromium_rollback_tested": False,
        "dependency_change_authorized": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--capture", action="store_true")
    modes.add_argument("--compare", type=Path, nargs=2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.capture and args.output is None:
        parser.error("--capture requires --output")
    if args.compare and args.output is not None:
        parser.error("--compare does not write evidence")
    try:
        if args.capture:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as browser:
                chromium = Path(browser.chromium.executable_path)
            record = snapshot(chromium)
            private_write(args.output, record)
            print("DEPENDENCY_748_CHROMIUM_LDD=HASHED_OBSERVED_NOT_ROLLBACK")
            print("DEPENDENCY_748_RESOLVED_LIBRARY_COUNT=" + str(len(record["libraries"])))
        else:
            result = compare(*(private_read(p) for p in args.compare))
            print(json.dumps(result, sort_keys=True))
            if not result["matching_host_fingerprints"]:
                return 2
    except (HostEvidenceError, OSError, TypeError, ValueError, KeyError,
            subprocess.TimeoutExpired) as exc:
        print("DEPENDENCY_748_EVIDENCE=BLOCKED_" + type(exc).__name__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
