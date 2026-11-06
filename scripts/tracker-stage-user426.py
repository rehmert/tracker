#!/usr/bin/env python3
"""Preview or explicitly stage an inactive secondary-user workspace."""

import argparse
import os
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.user_bootstrap426 import (
    initialize_staged_workspace426,
    verify_staged_workspace426,
)
from app.user_storage388 import planned_storage


def configured_instance_and_root():
    settings = {}

    for line in Path('/etc/tracker.env').read_text().splitlines():
        match = re.match(
            r'^\s*(?:export\s+)?'
            r'(TRACKER_INSTANCE|TRACKER_DATA_DIR)\s*=(.*)$',
            line,
        )

        if not match:
            continue

        values = shlex.split(
            match.group(2), comments=False
        )

        if len(values) != 1:
            raise ValueError(
                "Invalid Tracker environment configuration"
            )

        name = match.group(1)

        if name in settings:
            raise ValueError(
                "Duplicate Tracker environment setting"
            )

        settings[name] = values[0]

    raw = settings.get(
        "TRACKER_DATA_DIR", str(ROOT / "data")
    )

    directory = Path(raw)

    if not directory.is_absolute():
        directory = ROOT / directory

    return (
        settings.get("TRACKER_INSTANCE", "").upper(),
        directory.absolute(),
    )


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--user-id", type=int, required=True
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Explicitly initialize a private, inactive "
            "workspace on the configured DEV host"
        ),
    )

    parser.add_argument(
        "--verify",
        action="store_true",
        help="Read-only verification of an existing staged workspace",
    )

    args = parser.parse_args()

    if args.apply and args.verify:
        parser.error("--apply and --verify are mutually exclusive")

    instance, root = configured_instance_and_root()

    if instance != "DEV":
        raise SystemExit(
            "Only DEV is supported by this staging command"
        )

    if args.user_id <= 1:
        raise SystemExit(
            "Only secondary numeric user IDs are supported"
        )

    paths = planned_storage(args.user_id, root)

    if args.verify:
        report = verify_staged_workspace426(
            args.user_id, root
        )
        print("PASS:", report)
        return

    if not args.apply:
        print("=== DRY RUN: NO USER WORKSPACE CREATED ===")
        print("User ID:", args.user_id)
        print("Database:", paths.database)
        print("COA attachments:", paths.coa)
        print("Lab attachments:", paths.labs)
        print("Backups:", paths.backups)
        print("Status: INACTIVE")
        print("To stage, rerun with --apply")
        return

    if os.geteuid() != 0:
        raise SystemExit(
            "Explicit staging requires root"
        )

    initialize_staged_workspace426(
        args.user_id, root
    )

    print(
        "PASS: Schema-ready inactive workspace created"
    )
    print(
        "User ID:", args.user_id
    )
    print(
        "Status: INACTIVE — NO LOGIN OR HTTP ACCESS"
    )


if __name__ == "__main__":
    main()
