#!/usr/bin/env python3
"""Bootstrap the one DEV admin from existing Basic Auth credentials."""

import os
import shlex
import sys
from pathlib import Path


def read_settings():
    values = {}

    for line in Path("/etc/tracker.env").read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[7:].strip()

        if "=" not in line:
            continue

        key, raw = line.split("=", 1)
        key = key.strip()

        if key not in {
            "TRACKER_INSTANCE",
            "TRACKER_USER",
            "TRACKER_PASS",
            "TRACKER_DATA_DIR",
        }:
            continue

        parsed = shlex.split(raw, comments=False)

        if len(parsed) != 1:
            raise ValueError(f"Invalid configuration: {key}")

        values[key] = parsed[0]

    return values


def main():
    values = read_settings()

    if values.get("TRACKER_INSTANCE", "").upper() != "DEV":
        raise ValueError("DEV identity required")

    username = values.get("TRACKER_USER", "")
    password = values.get("TRACKER_PASS", "")

    if not username or not password:
        raise ValueError("Existing credentials are required")

    directory = Path(
        values.get("TRACKER_DATA_DIR")
        or "/opt/tracker/data"
    ).resolve()

    os.environ["TRACKER_INSTANCE"] = "DEV"
    os.environ["TRACKER_DATA_DIR"] = str(directory)

    from app import session_auth385 as auth

    if (directory / auth.FLAG).exists():
        raise ValueError("Session login already enabled")

    auth.bootstrap(username, password)
    print("PASS: Separate admin authentication store created")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
