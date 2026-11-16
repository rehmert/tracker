#!/usr/bin/env python3
"""One-off Release 644 recovery from failed 643 promotion; DEV-only and fail-closed.

No changes to the qualified Release 644 commit. Default is read-only preflight
except Git fetch. --execute signs target, makes a normal fast-forward push,
and invokes the installed, qualified production deployment workflow.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

APP = Path("/opt/tracker")
ROOT = Path("/etc/tracker-release")
RELEASE = 644
PROD_BASE = "92f6193f509abcb12fd4c9a2f4c8d11854822044"
PROMOTED_643 = "c7335b409724999195364fa02ce344e41a5a0405"
TARGET = "5bc0894c2c2865856856298083ca21bc62d00069"
REF = "release/644-coa-csrf-inventory"


def fail(message: str) -> None:
    raise RuntimeError(message)


def load_qualified_promoter():
    source = APP / "scripts/tracker_promote568.py"
    spec = importlib.util.spec_from_file_location("qualified_tracker_promoter", source)
    if spec is None or spec.loader is None:
        fail("Installed qualified promotion module unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true",
                        help="Explicitly sign, fast-forward GitHub main and deploy PROD")
    args = parser.parse_args()
    promoted = False
    try:
        promo = load_qualified_promoter()
        promo.validate(RELEASE, TARGET, PROD_BASE, REF)
        if os.geteuid() != 0 or promo.output(["hostname", "-s"]) != "tracker-dev":
            fail("Must run as root on tracker-dev")
        if promo.git("branch", "--show-current") != "main":
            fail("DEV must be on installed main")
        if promo.git("status", "--porcelain"):
            fail("DEV checkout must be clean")
        if promo.git("rev-parse", "HEAD") != TARGET:
            fail("Installed DEV commit does not match qualified 644 target")
        if promo.output(["systemctl", "is-active", "tracker"]) != "active":
            fail("DEV Tracker service not active")
        log = ROOT / "release-644-dev.log"
        promo.secure_file(log, private=True)
        promo.verified_log(log.read_text(encoding="utf-8"), TARGET)
        promo.secure_file(ROOT / "signing/dev-signing-private.pem", private=True)
        promo.secure_file(ROOT / "dev-signing-public.pem")
        promo.secure_file(APP / "scripts/tracker_prod_remote568.sh")

        # Recognize ONLY the specific interruption left by failed Release 643.
        promo.run(["git", "-c", f"safe.directory={APP}", "-C", str(APP),
                   "fetch", "origin", "main",
                   f"refs/heads/{REF}:refs/remotes/origin/{REF}"])
        main_sha = promo.git("rev-parse", "origin/main")
        release_sha = promo.git("rev-parse", f"refs/remotes/origin/{REF}")
        if main_sha != PROMOTED_643 or release_sha != TARGET:
            fail(f"Unexpected GitHub refs: main={main_sha}, release={release_sha}")
        for ancestor in (PROD_BASE, PROMOTED_643):
            promo.run(["git", "-c", f"safe.directory={APP}", "-C", str(APP),
                       "merge-base", "--is-ancestor", ancestor, TARGET])
        if promo.remote("hostname -s") != "tracker-prod":
            fail("Unexpected PROD destination")
        prod_sha = promo.remote(
            "git -c safe.directory=/opt/tracker -C /opt/tracker rev-parse HEAD"
        )
        if prod_sha != PROD_BASE:
            fail(f"PROD head changed unexpectedly: {prod_sha}")
        if promo.remote("systemctl is-active tracker") != "active":
            fail("PROD Tracker service not active")
        if promo.remote(
            "git -c safe.directory=/opt/tracker -C /opt/tracker branch --show-current"
        ) != "main":
            fail("PROD checkout is not main")
        if promo.remote(
            "git -c safe.directory=/opt/tracker -C /opt/tracker status --porcelain"
        ):
            fail("PROD checkout is dirty")

        print(f"RECOVERY_DEV_QUALIFIED={TARGET}", flush=True)
        print(f"RECOVERY_GITHUB_MAIN={main_sha}", flush=True)
        print(f"RECOVERY_PROD_INSTALLED={prod_sha}", flush=True)
        print("RECOVERY_ANCESTRY=PASSED", flush=True)
        print("RECOVERY_PREFLIGHT=PASSED", flush=True)
        if not args.execute:
            print("RECOVERY_DRY_RUN=PASSED (no signing, push, or deployment)", flush=True)
            return 0

        promo.sign_and_transfer(TARGET)
        # Ordinary fast-forward push only; no force, no resetting main.
        # The remote accepts this only while 643 remains an ancestor.
        promo.run(["git", "-c", f"safe.directory={APP}", "-C", str(APP),
                   "push", "origin", f"{TARGET}:refs/heads/main"])
        promoted = True
        promo.run(["git", "-c", f"safe.directory={APP}", "-C", str(APP),
                   "fetch", "origin", "main"])
        if promo.git("rev-parse", "origin/main") != TARGET:
            fail("GitHub main did not advance to exact qualified 644 commit")
        print(f"RECOVERY_PROMOTED_MAIN={TARGET}", flush=True)
        promo.deploy(RELEASE, TARGET, PROD_BASE)
        print("RECOVERY_644_PROD_DEPLOYMENT=SUCCESS", flush=True)
        return 0
    except Exception as exc:
        print(f"RECOVERY_ERROR={type(exc).__name__}: {exc}", file=sys.stderr)
        if promoted:
            print("PROMOTED_BUT_PROD_NOT_VERIFIED=YES", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
