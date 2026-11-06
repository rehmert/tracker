#!/usr/bin/env python3
"""Offline secondary-user probe. No listener or login is enabled."""

import argparse
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user-id", required=True, type=int
    )
    parser.add_argument(
        "--probe", action="store_true"
    )
    args = parser.parse_args()

    if os.geteuid() != 0:
        parser.error("Run as root")

    # Reuse Release 427's verified DEV configuration parser.
    env_script = (
        ROOT / "scripts"
        / "tracker-stage-account427.py"
    )

    _, root = runpy.run_path(
        str(env_script)
    )["configured_environment"]()

    os.environ["TRACKER_INSTANCE"] = "DEV"
    os.environ["TRACKER_DATA_DIR"] = str(root)

    sys.path.insert(0, str(ROOT))

    from app.worker_scope428 import (
        worker_plan428,
        run_worker_probe428,
    )

    private = worker_plan428(
        args.user_id, root
    )

    print(
        "User:", private.user_id,
        "Workspace:", private.root
    )
    print(
        "Status: INACTIVE; "
        "no HTTP or secondary-user login"
    )

    if args.probe:
        result = run_worker_probe428(
            args.user_id, root
        )
        print(
            "PASS: Isolated offline worker",
            result
        )
    else:
        print(
            "PASS: Read-only workspace preflight"
        )


if __name__ == "__main__":
    main()
