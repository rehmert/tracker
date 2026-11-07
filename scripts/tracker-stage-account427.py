#!/usr/bin/env python3
"""Stage disabled secondary credentials after provisioning a private workspace.

The command is a dry run unless --apply is supplied.
Passwords are read interactively, never from shell arguments.
"""

import argparse
import getpass
import os
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def configured_environment():
    settings = {}

    for line in Path('/etc/tracker.env').read_text().splitlines():
        match = re.match(
            r'^\s*(?:export\s+)?'
            r'(TRACKER_INSTANCE|TRACKER_DATA_DIR)\s*=(.*)$',
            line,
        )

        if match:
            values = shlex.split(
                match.group(2),
                comments=False,
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

    instance = settings.get("TRACKER_INSTANCE", "").upper()

    if instance != "DEV":
        raise PermissionError("DEV instance required")

    root = Path(
        settings.get("TRACKER_DATA_DIR", str(ROOT / "data"))
    )

    if not root.is_absolute():
        root = ROOT / root

    return instance, root.absolute()


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--user-id", type=int)
    parser.add_argument("--username")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--list", action="store_true")

    args = parser.parse_args()

    if sum((args.apply, args.verify, args.list)) > 1:
        parser.error(
            "--apply, --verify and --list are mutually exclusive"
        )

    if os.geteuid() != 0:
        raise SystemExit("Run as root")

    instance, data_root = configured_environment()

    # Configure paths BEFORE importing application modules.
    os.environ["TRACKER_INSTANCE"] = instance
    os.environ["TRACKER_DATA_DIR"] = str(data_root)

    sys.path.insert(0, str(ROOT))

    from app.user_accounts427 import (
        inspect_staged_account427,
        list_staged_accounts427,
        stage_secondary_account427,
        staging_environment,
        validate_username,
    )
    from app.user_bootstrap426 import verify_staged_workspace426

    staging_environment(data_root)

    if args.list:
        accounts = list_staged_accounts427()

        print("=== STAGED SECONDARY ACCOUNTS ===")

        for account in accounts:
            print(
                account["user_id"],
                account["username"],
                account["credential_status"],
                account["workspace_status"],
            )

        print("Total:", len(accounts))
        return

    if args.user_id is None or args.user_id <= 1:
        parser.error("--user-id must be greater than 1")

    if args.verify:
        print(
            "PASS:",
            inspect_staged_account427(
                args.user_id, data_root
            ),
        )
        return

    if not args.username:
        parser.error("--username is required")

    username = validate_username(args.username)

    print("=== SECONDARY ACCOUNT STAGING ===")
    print("User ID:", args.user_id)
    print("Username:", username)
    print("Access: DISABLED")

    if not args.apply:
        print("DRY RUN: No credentials created")
        print("Use --apply to stage the account")
        return

    verify_staged_workspace426(
        args.user_id, data_root
    )

    secret = getpass.getpass(
        "New secondary account password: "
    )
    confirmation = getpass.getpass(
        "Confirm password: "
    )

    if secret != confirmation:
        raise SystemExit("Passwords do not match")

    result = stage_secondary_account427(
        args.user_id,
        username,
        secret,
        data_root,
    )

    print("PASS: Secondary account staged")
    print("Account:", result["username"])
    print("Credential status: DISABLED")
    print("Application access: DISABLED")


if __name__ == "__main__":
    main()
