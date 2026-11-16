#!/usr/bin/env python3
"""Release 650: audit DEV-only unsynchronized attachment references read-only.

A missing file in DEV is not proof of damage in PROD. The existing Release
645 integrity scanner remains strict and unchanged. This wrapper can only
tolerate DEV *missing* file references, never malformed paths, present-file
hash mismatches, scan exceptions, or any PROD deployment condition.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "scripts/tracker-attachment-integrity645.py"
COUNTS = (
    "ATTACHMENT_REFERENCES_CHECKED",
    "ATTACHMENT_FILES_MISSING",
    "ATTACHMENT_REFERENCES_INVALID",
    "ATTACHMENT_HASH_MISMATCHES",
)
COUNT_LINE = re.compile(r"^(ATTACHMENT_[A-Z_]+)=(0|[1-9][0-9]*)$")
INSTANCE_LINE = re.compile(r"^\s*(?:export\s+)?TRACKER_INSTANCE\s*=(.*)$")


class DevAttachmentError(ValueError):
    pass


def classify(stdout: str, returncode: int) -> tuple[str, int]:
    """Fail closed unless the scanner reports missing files and nothing else."""
    matches: dict[str, int] = {}
    status: list[str] = []
    for line in stdout.splitlines():
        hit = COUNT_LINE.fullmatch(line)
        if hit and hit.group(1) in COUNTS:
            if hit.group(1) in matches:
                raise DevAttachmentError("Duplicate integrity counter")
            matches[hit.group(1)] = int(hit.group(2))
        elif line.startswith("ATTACHMENT_INTEGRITY="):
            status.append(line.partition("=")[2])
    if set(matches) != set(COUNTS) or len(status) != 1:
        raise DevAttachmentError("Missing or duplicate integrity evidence")
    if status[0] not in ("PASSED", "FAILED"):
        raise DevAttachmentError("Unknown integrity status")
    checked = matches["ATTACHMENT_REFERENCES_CHECKED"]
    missing = matches["ATTACHMENT_FILES_MISSING"]
    invalid = matches["ATTACHMENT_REFERENCES_INVALID"]
    mismatch = matches["ATTACHMENT_HASH_MISMATCHES"]
    if checked < missing + invalid + mismatch:
        raise DevAttachmentError("Impossible attachment counters")
    if invalid or mismatch:
        raise DevAttachmentError(
            f"Invalid references={invalid}, present-file hash mismatches={mismatch}"
        )
    if not missing and returncode == 0 and status[0] == "PASSED":
        return "PASSED", 0
    if missing and returncode == 1 and status[0] == "FAILED":
        if stdout.count("MISSING_REFERENCE table=") != missing:
            raise DevAttachmentError("Missing-file detail/count disagreement")
        return "DEV_MISSING_ALLOWED", missing
    raise DevAttachmentError(
        "Scanner return code/status inconsistent with missing-file-only policy"
    )


def verify_dev_instance(config_path: Path = Path("/etc/tracker.env")) -> None:
    """No accidental use on PROD, even if caller passes an override."""
    entries = []
    for line in config_path.read_text(encoding="utf-8").splitlines():
        match = INSTANCE_LINE.match(line)
        if match:
            entries.append(match.group(1).strip().strip('"').strip("'").upper())
    if entries != ["DEV"]:
        raise DevAttachmentError("DEV-only attachment allowance is prohibited on PROD")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        verify_dev_instance()
        scanner = subprocess.run(
            [sys.executable, str(SCANNER), "--data", str(args.data), "--hashes"],
            capture_output=True, text=True, check=False, timeout=120,
        )
        if scanner.stdout:
            print(scanner.stdout, end="")
        if scanner.stderr:
            print(scanner.stderr, file=sys.stderr, end="")
        outcome, count = classify(scanner.stdout, scanner.returncode)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"DEV_ATTACHMENT_GATE=FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"DEV_ATTACHMENT_GATE={outcome}")
    if count:
        print(f"DEV_MISSING_REFERENCES_NOT_REPAIRED={count}")
        print("DEV_MISSING_FILES=NOT_SYNCED_FROM_PROD")
        print("DEV_PRESENT_FILE_HASHES=PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
