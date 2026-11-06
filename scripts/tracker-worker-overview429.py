#!/usr/bin/env python3
"""Read-only overview of an inactive workspace; no network listener."""

import argparse
import os
import runpy
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", required=True, type=int)
    parser.add_argument("--overview", action="store_true")
    args = parser.parse_args()

    if os.geteuid() != 0:
        raise SystemExit("Run as root")

    _, root = runpy.run_path(str(
        ROOT / "scripts" / "tracker-stage-account427.py"
    ))["configured_environment"]()

    os.environ["TRACKER_INSTANCE"] = "DEV"
    os.environ["TRACKER_DATA_DIR"] = str(root)

    sys.path.insert(0, str(ROOT))

    from app.worker_scope428 import worker_plan428
    from app.worker_request429 import read_workspace_overview429

    plan = worker_plan428(args.user_id, root)

    print(
        f"User {plan.user_id}: inactive, "
        f"private workspace {plan.root}"
    )

    if not args.overview:
        print("PASS: Preflight only; use --overview for private counts")
        return

    report = read_workspace_overview429(args.user_id, root)

    print("PASS: Private, read-only subprocess")

    for key, value in report["counts"].items():
        print(f"  {key}: {value}")

    print("HTTP access: DISABLED")


if __name__ == "__main__":
    main()
