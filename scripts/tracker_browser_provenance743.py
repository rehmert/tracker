#!/usr/bin/env python3
"""Release 743: immutable read-only Chromium+Python+OS provenance fingerprints.

This complements (does not replace) the approved Release 705 SHA-locked Python
wheelhouse and independent offline replays. It never installs, downloads,
executes the browser, or claims a tested browser/OS rollback.
Output has NO host paths, environment variables, credentials or medical data.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys

from scripts.tracker_dependency_baseline569 import BASELINE, read_manifest

SHA = re.compile(r"[0-9a-f]{64}\Z")
FIELDS = frozenset({
    "schema", "python", "playwright", "chromium_sha256", "chromium_bytes",
    "os_id", "os_version", "libc_name", "libc_version",
})
REPORT_LIMIT = 4096


class BrowserEvidenceError(ValueError):
    pass


def hash_binary(path: Path) -> tuple[str, int]:
    if path.is_symlink():
        raise BrowserEvidenceError("Chromium binary cannot be a symlink")
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_size < 1:
        raise BrowserEvidenceError("Expected a nonempty regular Chromium executable")
    # Don't open arbitrary host data: browser evidence is an explicit operator
    # action and is never run against an untrusted request-supplied web path.
    h = sha256()
    with path.open("rb") as file:
        while data := file.read(1024 * 1024):
            h.update(data)
    if path.stat().st_size != st.st_size:
        raise BrowserEvidenceError("Chromium changed while being fingerprinted")
    return h.hexdigest(), st.st_size


def os_details() -> tuple[str, str]:
    try:
        info = platform.freedesktop_os_release()
    except OSError:
        raise BrowserEvidenceError("OS release information unavailable") from None
    os_id = info.get("ID", "")
    os_ver = info.get("VERSION_ID", "")
    if not re.fullmatch(r"[a-z0-9._-]{1,48}", os_id):
        raise BrowserEvidenceError("OS identity malformed")
    if not re.fullmatch(r"[A-Za-z0-9._+-]{1,48}", os_ver):
        raise BrowserEvidenceError("OS version malformed")
    return os_id, os_ver


def snapshot(chromium: Path, *, py: str | None = None,
             playwright: str | None = None,
             operating_system: tuple[str, str] | None = None,
             libc: tuple[str, str] | None = None) -> dict:
    checksum, length = hash_binary(chromium)
    os_id, os_ver = operating_system if operating_system is not None else os_details()
    libc_name, libc_ver = libc if libc is not None else platform.libc_ver()
    return {
        "schema": 1,
        "python": py if py is not None else platform.python_version(),
        "playwright": playwright if playwright is not None else version("playwright"),
        "chromium_sha256": checksum,
        "chromium_bytes": length,
        "os_id": os_id, "os_version": os_ver,
        "libc_name": libc_name, "libc_version": libc_ver,
    }


def validate(report: dict) -> dict:
    if not isinstance(report, dict) or set(report) != FIELDS or report.get("schema") != 1:
        raise BrowserEvidenceError("Invalid browser provenance schema")
    if not isinstance(report["chromium_sha256"], str) or not SHA.fullmatch(report["chromium_sha256"]):
        raise BrowserEvidenceError("Invalid Chromium SHA-256")
    n = report["chromium_bytes"]
    if type(n) is not int or n < 1:
        raise BrowserEvidenceError("Invalid Chromium byte count")
    for name in FIELDS - {"schema", "chromium_sha256", "chromium_bytes"}:
        v = report[name]
        if not isinstance(v, str) or not re.fullmatch(r"[a-zA-Z0-9_.+-]{1,80}", v):
            raise BrowserEvidenceError("Invalid runtime fingerprint attribute")
    return report


def read_receipt(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > REPORT_LIMIT:
        raise BrowserEvidenceError("Expected a small regular sanitized receipt")
    return validate(json.loads(path.read_text(encoding="utf-8")))


def write_private(path: Path, report: dict) -> None:
    parent = path.parent
    if (parent.is_symlink() or not parent.is_dir()
            or not parent.resolve().is_relative_to(Path("/tmp"))
            or parent.stat().st_mode & 0o077):
        raise BrowserEvidenceError("Receipt requires a private /tmp directory")
    data = (json.dumps(validate(report), sort_keys=True, indent=2) + "\n").encode()
    if len(data) > REPORT_LIMIT:
        raise BrowserEvidenceError("Fingerprint exceeds size limit")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())


def compare(dev: dict, prod: dict) -> dict:
    baseline = read_manifest(BASELINE)
    validate(dev); validate(prod)
    equality = all(dev[name] == prod[name] for name in FIELDS - {"schema"})
    pinned = all(
        result["python"] == baseline["python"]
        and result["playwright"] == baseline["packages"]["playwright"]
        for result in (dev, prod)
    )
    return {
        "schema": 1,
        "dev_prod_browser_python_os_identical": equality,
        "matching_approved_python_playwright_baseline": pinned,
        "fingerprints_equal": equality and pinned,
        "chromium_downloaded_by_this_tool": False,
        "browser_qa_full_http_https_certified": False,
        "os_dependency_rollback_tested": False,
        "supply_chain_independently_reviewed": False,
        "issue10_closed": False,
        "decision": "BLOCKED_PENDING_BROWSER_AND_OS_ROLLBACK_EVIDENCE",
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    modes = p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--capture", type=Path, help="Explicit existing Chromium executable")
    modes.add_argument("--compare", nargs=2, metavar=("DEV_JSON", "PROD_JSON"),
                       type=Path)
    p.add_argument("--output", type=Path, help="Write a private /tmp JSON receipt, never GitHub")
    p.add_argument("--require-complete", action="store_true",
                   help="Fail without independent browser, OS and rollback clearance")
    args = p.parse_args(argv)
    if args.compare is not None and args.output is not None:
        p.error("--output may only be used with --capture")
    try:
        if args.capture is not None:
            report = validate(snapshot(args.capture))
        else:
            report = compare(*(read_receipt(path) for path in args.compare))
        if args.output is not None:
            write_private(args.output, report)
        else:
            print(json.dumps(report, sort_keys=True))
    except (BrowserEvidenceError, OSError, ValueError, KeyError, TypeError) as err:
        print("BROWSER_743_AUDIT=ERROR_"+type(err).__name__, file=sys.stderr)
        return 2
    if args.require_complete:
        print("BROWSER_743_ISSUE10=BLOCKED_PENDING_REVIEWED_ROLLBACK")
        return 3
    print("BROWSER_743_AUDIT=PASS_READ_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
