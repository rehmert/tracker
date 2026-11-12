#!/usr/bin/env python3
"""Persist exact-commit DEV qualification evidence, never fabricate missing tests.

Called only by the guarded release worker after success. Refuses unrelated
paths, symlinks, incomplete logs, unsafe permissions or inconsistent SHAs.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import stat
import tempfile

REQUIRED = (
    "ISOLATED_BROWSER=PASSED",
    "ISOLATED_STRICT_CSRF_BROWSER=PASSED",
    "=== ALL BACKEND TESTS PASSED ===",
    "=== ISOLATED RESTORE VERIFICATION PASSED ===",
)
SHA = re.compile(r"[0-9a-f]{40}\Z")


def validated_evidence(content: str, target: str) -> str:
    if not SHA.fullmatch(target):
        raise ValueError("Invalid target SHA")
    lines = content.splitlines()
    for marker in (*REQUIRED, f"CANDIDATE_COMMIT={target}"):
        if marker not in lines:
            raise ValueError(f"Missing DEV qualification evidence: {marker}")
    if not any("TRACKER RELEASE DEPLOYMENT SUCCESS" in line for line in lines):
        raise ValueError("Missing guarded deployment success")
    statuses = [line for line in lines if line.startswith("EXIT_STATUS=")]
    if statuses != ["EXIT_STATUS=0"]:
        raise ValueError("Expected exactly one successful final exit status")
    if any(line.startswith("DEV_QUALIFIED_COMMIT=") for line in lines):
        raise ValueError("Original log must not contain injected qualification marker")
    if "Finished: " not in content:
        raise ValueError("Original log lacks completion timestamp")
    return content.rstrip("\n") + f"\nDEV_QUALIFIED_COMMIT={target}\n"


def secure_dir(path: Path, create: bool = False) -> None:
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
        raise ValueError("Qualification directory must be root-owned, private and non-symlinked")


def preserve(source: Path, dest_dir: Path, release: int, target: str) -> Path:
    if os.geteuid() != 0 or os.uname().nodename.split(".")[0] != "tracker-dev":
        raise ValueError("DEV root only")
    if release < 1 or release > 999999:
        raise ValueError("Invalid release number")
    if not SHA.fullmatch(target):
        raise ValueError("Invalid SHA")
    if source.name != "deployment.log" or source.parent.parent != Path("/tmp/tracker-backups"):
        raise ValueError("Unexpected guarded deployment log path")
    if not re.fullmatch(r"release\.[a-zA-Z0-9]{8}", source.parent.name):
        raise ValueError("Unexpected release workspace")
    secure_dir(source.parent)
    info = source.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
        raise ValueError("Guarded log must be root-owned, private, regular")
    evidence = validated_evidence(source.read_text(encoding="utf-8"), target)
    secure_dir(dest_dir, create=True)
    dest = dest_dir / f"release-{release}-dev.log"
    if dest.exists() or dest.is_symlink():
        raise ValueError("Qualification receipt already exists: refusing overwrite")
    # Exclusive private staging + atomic publish; no writable partial log.
    fd, name = tempfile.mkstemp(prefix=f".release-{release}-", dir=dest_dir)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            os.fchmod(out.fileno(), 0o600)
            out.write(evidence)
            out.flush()
            os.fsync(out.fileno())
        # Fail if an unexpected file appeared, rather than replacing it.
        os.link(tmp, dest, follow_symlinks=False)
    finally:
        tmp.unlink(missing_ok=True)
    return dest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--release", type=int, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--destination-dir", type=Path, default=Path("/etc/tracker-release"))
    args = parser.parse_args(argv)
    try:
        dest = preserve(args.source, args.destination_dir, args.release, args.target)
    except (OSError, ValueError, UnicodeError) as exc:
        parser.error(str(exc))
    print(f"DEV_QUALIFICATION_EVIDENCE_PRESERVED={dest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
