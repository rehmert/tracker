#!/usr/bin/env python3
"""DEV-controlled staged promotion of historical Workout 654–657 releases.

Runs exclusively on tracker-dev. Uses DEV's installed, trusted Release 568
signing/promotion functions, pinned historical DEV qualification receipts,
and a reviewed remote executor streamed over strict BatchMode SSH. No user
needs to open a shell on PROD. Default is a read-only release preflight.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

APP = Path("/opt/tracker")
ROOT = Path("/etc/tracker-release")
sys.path.insert(0, str(APP / "scripts"))
import tracker_promote568 as ops  # noqa: E402

STAGES = {
    654: (
        "108bf3241bd747f6174dc7e65a8c01161af24e62",
        "419e0c199d6a5dc373df7de1401953a056cac8d1",
        "release/654-workout-foundation",
    ),
    655: (
        "419e0c199d6a5dc373df7de1401953a056cac8d1",
        "b1d8ad1d3003d1f8ef2e5b3614ba1148076c5c25",
        "release/655-workout-routines-fast-logging",
    ),
    656: (
        "b1d8ad1d3003d1f8ef2e5b3614ba1148076c5c25",
        "06b8be62f5be455df47be87bc5157b41fcac8783",
        "release/656-workout-qr-progress",
    ),
    657: (
        "06b8be62f5be455df47be87bc5157b41fcac8783",
        "b9487d4b1fab176255b398833c51c9a2da79f042",
        "release/657-workout-edit-next-machine",
    ),
}
DEV_INSTALLED = STAGES[657][1]


def check(release: int) -> tuple[str, str]:
    base, target, ref = STAGES[release]
    if os.geteuid() != 0 or ops.output(["hostname", "-s"]) != "tracker-dev":
        raise ops.ReleaseError("Run as root on tracker-dev only")
    subprocess.run([
        str(APP / ".venv/bin/python"),
        str(APP / "scripts/tracker-instance-check653.py"),
        "--config", "/etc/tracker.env",
    ], check=True)
    if ops.git("branch", "--show-current") != "main":
        raise ops.ReleaseError("DEV installed branch must be main")
    if ops.git("status", "--porcelain"):
        raise ops.ReleaseError("DEV checkout must be clean")
    current = ops.git("rev-parse", "HEAD")
    if current != DEV_INSTALLED:
        raise ops.ReleaseError(
            "DEV installation must be the approved Release 657 commit"
        )
    if ops.output(["systemctl", "is-active", "tracker"]) != "active":
        raise ops.ReleaseError("DEV tracker service inactive")

    log = ROOT / f"release-{release}-dev.log"
    ops.secure_file(log, private=True)
    ops.verified_log(log.read_text(encoding="utf-8"), target)

    ops.run([
        "git", "-c", f"safe.directory={APP}", "-C", str(APP),
        "fetch", "origin", "main",
        f"refs/heads/{ref}:refs/remotes/origin/{ref}",
    ])
    head = ops.git("rev-parse", f"refs/remotes/origin/{ref}")
    if head != target:
        raise ops.ReleaseError("Qualified release branch changed unexpectedly")
    main = ops.git("rev-parse", "origin/main")
    if main not in (base, target):
        raise ops.ReleaseError("GitHub main is not the expected promotion stage")

    ops.run([
        "git", "-c", f"safe.directory={APP}", "-C", str(APP),
        "merge-base", "--is-ancestor", base, target,
    ])
    ops.run([
        "git", "-c", f"safe.directory={APP}", "-C", str(APP),
        "merge-base", "--is-ancestor", target, current,
    ])

    if ops.remote("hostname -s") != "tracker-prod":
        raise ops.ReleaseError("PROD SSH destination identity mismatch")
    prod_head = ops.remote(
        "git -c safe.directory=/opt/tracker -C /opt/tracker rev-parse HEAD"
    )
    if prod_head not in (base, target):
        raise ops.ReleaseError("PROD installed SHA is not this promotion stage")
    if ops.remote("systemctl is-active tracker") != "active":
        raise ops.ReleaseError("PROD service inactive")

    ops.secure_file(ROOT / "signing/dev-signing-private.pem", private=True)
    ops.secure_file(ROOT / "dev-signing-public.pem")
    script = Path(__file__).resolve().with_name(
        "tracker-workout-prod-remote657.sh"
    )
    ops.secure_file(script, private=True)

    print(f"DEV_QUALIFIED={target}", flush=True)
    print(f"DEV_INSTALLED={current}", flush=True)
    print(f"GITHUB_MAIN={main}", flush=True)
    print(f"PROD_INSTALLED={prod_head}", flush=True)
    print(f"WORKOUT_STAGE={release}", flush=True)
    print("STAGED_PREFLIGHT=PASSED", flush=True)
    return base, target


def execute(release: int, base: str, target: str) -> None:
    ops.sign_and_transfer(target)
    ops.promote(target, base)
    script = Path(__file__).resolve().with_name(
        "tracker-workout-prod-remote657.sh"
    )
    ops.run([
        *ops.SSH, "-T", ops.PROD, "bash", "-s", "--",
        base, target, str(release),
    ], input_data=script.read_bytes())

    final = ops.remote(
        "git -c safe.directory=/opt/tracker -C /opt/tracker rev-parse HEAD"
    )
    if final != target or ops.remote("systemctl is-active tracker") != "active":
        raise ops.ReleaseError("PROD post-deployment verification failed")
    print(f"PROD_INSTALLED_COMMIT={target}", flush=True)
    print(f"WORKOUT_STAGE_{release}=SUCCESS", flush=True)
    print("DEV_CONTROLLED_RELEASE=SUCCESS", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=int, choices=tuple(STAGES), required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    promoted = False
    try:
        base, target = check(args.release)
        if not args.execute:
            print("STAGED_DRY_RUN=PASSED (no approval or deploy)", flush=True)
            return 0
        ops.sign_and_transfer(target)
        ops.promote(target, base)
        promoted = True
        script = Path(__file__).resolve().with_name(
            "tracker-workout-prod-remote657.sh"
        )
        ops.run([
            *ops.SSH, "-T", ops.PROD, "bash", "-s", "--",
            base, target, str(args.release),
        ], input_data=script.read_bytes())
        final = ops.remote(
            "git -c safe.directory=/opt/tracker -C /opt/tracker rev-parse HEAD"
        )
        if final != target or ops.remote("systemctl is-active tracker") != "active":
            raise ops.ReleaseError("PROD post-deployment verification failed")
        print(f"PROD_INSTALLED_COMMIT={target}", flush=True)
        print(f"WORKOUT_STAGE_{args.release}=SUCCESS", flush=True)
        print("DEV_CONTROLLED_RELEASE=SUCCESS", flush=True)
        return 0
    except (ops.ReleaseError, OSError, UnicodeError, subprocess.CalledProcessError) as exc:
        print(f"STAGED_RELEASE_ERROR={exc}", file=sys.stderr)
        if promoted:
            print("PROMOTED_BUT_PROD_NOT_VERIFIED=YES", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
