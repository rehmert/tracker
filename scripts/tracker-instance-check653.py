#!/usr/bin/env python3
"""Release 653: fail-closed, redacted DEV instance check for deployment scripts.

A configured instance value may be followed by a shell comment. Validate the
literal value without echoing /etc/tracker.env (which may contain secrets).
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import shlex
import socket
import sys

_ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?TRACKER_INSTANCE\s*=\s*(.*)$")


def parse_instance_values(content: str) -> list[str]:
    """Extract instance assignments from shell-style .env lines, fail closed."""
    result: list[str] = []
    for line in content.splitlines():
        match = _ASSIGNMENT.match(line)
        if match is None:
            continue
        try:
            words = shlex.split(match.group(1), comments=True, posix=True)
        except ValueError as exc:
            raise ValueError("Malformed TRACKER_INSTANCE assignment") from exc
        if len(words) != 1:
            raise ValueError("TRACKER_INSTANCE must be one value")
        result.append(words[0].strip().upper())
    return result


def verify_dev(config: Path = Path("/etc/tracker.env"),
               hostname: str | None = None) -> None:
    host = hostname if hostname is not None else socket.gethostname().split(".")[0]
    if host != "tracker-dev":
        raise ValueError("Expected tracker-dev hostname")
    values = parse_instance_values(config.read_text(encoding="utf-8"))
    if len(values) != 1:
        raise ValueError("Expected exactly one TRACKER_INSTANCE entry")
    if values != ["DEV"]:
        raise ValueError("TRACKER_INSTANCE is not DEV")
    print("RELEASE_653_DEV_IDENTITY=VERIFIED")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("/etc/tracker.env"))
    args = parser.parse_args()
    try:
        verify_dev(config=args.config)
    except (OSError, ValueError) as exc:
        print("RELEASE_653_DEV_IDENTITY=FAILED: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
