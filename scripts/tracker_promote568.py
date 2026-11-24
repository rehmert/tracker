#!/usr/bin/env python3
"""DEV-only, explicitly authorized signed promotion and PROD deployment.

GitHub is version control only; DEV and PROD perform their own guarded tests.
Default mode is read-only preflight (apart from git fetch of remote refs).
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

APP = Path("/opt/tracker")
ROOT = Path("/etc/tracker-release")
PROD = "root@tracker-prod"
SHA = re.compile(r"[0-9a-f]{40}\Z")
REF = re.compile(r"release/([1-9][0-9]{0,5})-[a-zA-Z0-9._/-]+\Z")
SSH = [
    "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
    "-o", "StrictHostKeyChecking=yes", "-o", "ClearAllForwardings=yes",
    "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=6",
]
SCP = [
    "scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
    "-o", "StrictHostKeyChecking=yes",
]
# Release 648 only: GitHub main contains signed Release 647 even though
# PROD did not install it. Only this exact ancestor may be skipped when
# advancing main; PROD itself must still match the installed Release 646 base.
RECOVERY_648_MAIN = "cd041ba1dfefe6e2de7db72c8bfdf8f9949e6dc6"
RECOVERY_648_PROD_BASE = "61b3016eed48527c61a5173d94ee0f58b859f81a"
# Release 677: Release 676 was promoted to main but rejected by PROD's
# focused CSS serialization assertion. Recovery may skip only this exact
# approved-but-not-installed 676 main commit, from exact installed 675 base.
RECOVERY_677_MAIN = "3646f5ebf39f0b0ff2759c35e75df46120a72c7c"
RECOVERY_677_PROD_BASE = "2e8f65d7c61c522a5ab01f78cd3783e15559ece3"
# Release 705 catch-up: DEV/GitHub main has qualified UX Releases 694–704,
# while PROD may still be at qualified Release 693 or a later ancestor.
# This is a ONE-RELEASE, exact-main, exact-file-scope exception; it never
# bypasses the signed DEV receipt, exact PROD base, or fast-forward-only push.
RECOVERY_705_MAIN = "24cb9ec47417e001c3f96dfed630e3b8b0264d93"
RECOVERY_705_PROD_FLOOR = "4d752be1a62ffa8a5feba78a50033e980a30b26c"
RECOVERY_705_REF = "refs/remotes/origin/release/705-csrf-dependency-closeout"
# Release 768 only: GitHub main was promoted to 767, but the immutable
# r767-deploy5d23aaf4 receipt failed *before* any PROD install. PROD remains
# at Release 765. A new SHA fixes the validated relative data directory.
RECOVERY_768_MAIN = "5d23aaf4f7e7fa4b54c1d5535a622bdd9e9aac13"
RECOVERY_768_PROD_BASE = "8c67580611fd945d9ae83f8015f071a24ab6fee5"
RECOVERY_768_REF = "refs/remotes/origin/release/768-prod-relative-data-path-recovery"
RECOVERY_705_ALLOWED = frozenset({
    "docs/release-705-csrf-dependency-closeout.md",
    "scripts/tracker-browser-preview705.sh",
    "scripts/tracker-browser-qualify.sh",
    "scripts/tracker-dependency-acquire705.sh",
    "scripts/tracker-dependency-preview705.sh",
    "scripts/tracker-dependency-replay705.sh",
    "scripts/tracker-preview705.sh",
    "scripts/tracker-release-scoped705.sh",
    "scripts/tracker_csrf_closeout705.py",
    "scripts/tracker_csrf_reconcile627.py",
    "scripts/tracker_csrf_runtime_report579.py",
    "scripts/tracker_dependency_acquire705.py",
    "scripts/tracker_dependency_lock705.py",
    "scripts/tracker_dependency_readiness705.py",
    "scripts/tracker_dependency_replay705.py",
    "scripts/tracker_promote568.py",
    "tests/browser/test_csrf_preparations583.py",
    "tests/browser/test_csrf_workflows580.py",
    "tests/browser/test_strict_csrf521.py",
    "tests/browser/test_vitals_proxy_host522.py",
    "tests/test_coa_multiple_test_types651.py",
    "tests/test_csrf_all_registered_negative705.py",
    "tests/test_release575_csrf_js_review.py",
    "tests/test_release576_csrf_js_triage.py",
    "tests/test_release578_csrf_route_ledger.py",
    "tests/test_release579_csrf_runtime_report.py",
    "tests/test_release627_csrf_reconciliation.py",
    "tests/test_release640_csrf_inventory.py",
    "tests/test_release648_prod_recovery.py",
    "tests/test_release705_combined.py",
    "tests/test_release705_dependency_acquire.py",
    "tests/test_release705_dependency_readiness.py",
    "tests/test_release705_dependency_replay.py",
    "tests/test_release705_promotion_catchup.py",
    "tests/test_release705_runtime_preview.py",
})


QUALIFICATION = (
    "ISOLATED_BROWSER=PASSED",
    "ISOLATED_STRICT_CSRF_BROWSER=PASSED",
    "=== ALL BACKEND TESTS PASSED ===",
    "=== ISOLATED RESTORE VERIFICATION PASSED ===",
)


class ReleaseError(RuntimeError):
    pass


def validate(release: int, target: str, base: str, ref: str) -> None:
    if not (1 <= release <= 999999):
        raise ReleaseError("Release number out of range")
    if not (SHA.fullmatch(target) and SHA.fullmatch(base)):
        raise ReleaseError("Both commit IDs must be exact 40-character lowercase SHAs")
    if target == base:
        raise ReleaseError("Target and PROD base must differ")
    match = REF.fullmatch(ref)
    if not match or int(match.group(1)) != release or ".." in ref or "//" in ref:
        raise ReleaseError("Release branch must match release/<number>-<name>")


def verified_log(content: str, target: str) -> None:
    """Validate historical full and current focused DEV qualification receipts."""
    lines = content.splitlines()
    full = ("QA_FULL_REQUIRED=1" in lines or
            all(marker in lines for marker in QUALIFICATION[:3]))
    focused = "QA_FULL_REQUIRED=0" in lines
    if full == focused:
        raise ReleaseError("Ambiguous DEV qualification mode")
    if focused:
        required = ("FOCUSED_RELEASE_GATE=PASSED",)
        if not ("RELEASE_604_FOCUSED_PREFLIGHT=PASSED" in lines or
                "RELEASE_SCOPED_PREFLIGHT=PASSED" in lines):
            raise ReleaseError("Missing scoped release qualification evidence")
    else:
        required = QUALIFICATION[:3]
    for marker in required:
        if marker not in lines:
            raise ReleaseError(f"Missing DEV qualification marker: {marker}")
    restored = "=== ISOLATED RESTORE VERIFICATION PASSED ===" in lines
    skipped = "DATABASE_BACKUP=SKIPPED_NO_MIGRATION" in lines
    if restored == skipped:
        raise ReleaseError("Missing or ambiguous database-backup outcome")
    if skipped and "DATABASE_BACKUP=VERIFIED_FOR_MIGRATION" in lines:
        raise ReleaseError("Conflicting database-backup evidence")
    if not any("TRACKER RELEASE DEPLOYMENT SUCCESS" in line for line in lines):
        raise ReleaseError("Missing guarded deployment success heading")
    statuses = [line for line in lines if line.startswith("EXIT_STATUS=")]
    if statuses != ["EXIT_STATUS=0"]:
        raise ReleaseError("Exactly one successful DEV exit status required")
    exact = f"DEV_QUALIFIED_COMMIT={target}"
    if lines.count(exact) != 1:
        raise ReleaseError("Missing exact-commit DEV qualification marker")


def run(command: list[str], *, input_data: bytes | None = None) -> None:
    subprocess.run(command, check=True, input=input_data)


def output(command: list[str]) -> str:
    return subprocess.check_output(command, text=True).strip()


def git(*args: str) -> str:
    return output(["git", "-c", f"safe.directory={APP}", "-C", str(APP), *args])


def remote(command: str) -> str:
    return output([*SSH, "-n", PROD, command])


def secure_file(path: Path, *, private: bool = False) -> None:
    if path.is_symlink() or not path.is_file():
        raise ReleaseError(f"Missing or symlinked required file: {path}")
    stat = path.stat()
    if stat.st_uid != 0 or stat.st_mode & 0o022:
        raise ReleaseError(f"Unsafe ownership or write permissions: {path}")
    if private and stat.st_mode & 0o077:
        raise ReleaseError(f"Private file is accessible to other users: {path}")


def recovery_648_main_allowed(main: str, target: str, base: str) -> bool:
    """Permit precisely the previously promoted-but-not-installed SHA.

    Never force push. Both ancestry checks fail closed if a ref is missing
    or another release has moved GitHub main.
    """
    if main != RECOVERY_648_MAIN or base != RECOVERY_648_PROD_BASE:
        return False
    try:
        run(["git", "-c", f"safe.directory={APP}", "-C", str(APP),
             "merge-base", "--is-ancestor", base, main])
        run(["git", "-c", f"safe.directory={APP}", "-C", str(APP),
             "merge-base", "--is-ancestor", main, target])
    except subprocess.CalledProcessError:
        return False
    return True


def recovery_677_main_allowed(main: str, target: str, base: str) -> bool:
    """Fail closed unless this is exactly the documented 676-to-677 recovery."""
    if main != RECOVERY_677_MAIN or base != RECOVERY_677_PROD_BASE:
        return False
    try:
        run(["git", "-c", f"safe.directory={APP}", "-C", str(APP),
             "merge-base", "--is-ancestor", base, main])
        run(["git", "-c", f"safe.directory={APP}", "-C", str(APP),
             "merge-base", "--is-ancestor", main, target])
    except subprocess.CalledProcessError:
        return False
    return True


def recovery_705_prod_lag_allowed(main: str, target: str, base: str) -> bool:
    """Exact Release 705 tooling-only catch-up, never a generic promotion bypass.

    Allow signed DEV main -> PROD only when PROD is at or after qualified
    Release 693, GitHub main remains immutable Release 704, and the Release
    705 delta is *exactly* the reviewed tooling/test/docs path inventory.
    """
    if (main != RECOVERY_705_MAIN or not SHA.fullmatch(target)
            or not SHA.fullmatch(base) or base == target):
        return False
    try:
        if git("rev-parse", RECOVERY_705_REF) != target:
            return False
        for ancestor, descendant in (
            (RECOVERY_705_PROD_FLOOR, base),
            (base, main),
            (main, target),
        ):
            run(["git", "-c", f"safe.directory={APP}", "-C", str(APP),
                 "merge-base", "--is-ancestor", ancestor, descendant])
        dev_delta = set(git("diff", "--name-only", main, target).splitlines())
        if dev_delta != RECOVERY_705_ALLOWED:
            return False
        # Never carry a schema/dependency migration over the PROD gap.
        prod_delta = set(git("diff", "--name-only", base, target).splitlines())
        if any(
            path.startswith(("deploy/", "alembic/"))
            or path.startswith("requirements")
            or path in (
                "alembic.ini", "app/db.py", "app/models.py",
                "app/migrations.py", "app/workout_models654.py",
                "app/workout_models655.py", "app/workout_models667.py",
                "app/workout_models668.py",
            )
            for path in prod_delta
        ):
            return False
    except (subprocess.CalledProcessError, ValueError, OSError):
        return False
    return True


def recovery_768_main_allowed(main: str, target: str, base: str) -> bool:
    """Exact, audited 767-promoted/765-installed recovery, never a generic skip."""
    if (main != RECOVERY_768_MAIN or base != RECOVERY_768_PROD_BASE
            or not SHA.fullmatch(target) or target == main):
        return False
    try:
        if git("rev-parse", RECOVERY_768_REF) != target:
            return False
        for ancestor, descendant in (
            (base, main), (main, target),
        ):
            run(["git", "-c", f"safe.directory={APP}", "-C", str(APP),
                 "merge-base", "--is-ancestor", ancestor, descendant])
        paths = set(git("diff", "--name-only", main, target).splitlines())
        # The already DEV-qualified 766 app bytes must remain untouched.
        if not paths or any(
            not path.startswith(("scripts/", "docs/", "tests/"))
            for path in paths
        ):
            return False
        source = git("show", f"{target}:scripts/tracker-prod-schema-backup767.py")
        if ("def resolve_data_dir768(" not in source
                or 'return resolve_data_dir768(Path("/opt/tracker"), Path("/etc/tracker.env"))' not in source):
            return False
        remote_guard = git("show", f"{target}:scripts/tracker_prod_remote568.sh")
        if '[[ "$RELEASE" == 767 || "$RELEASE" == 768 ]]' not in remote_guard:
            return False
    except (subprocess.CalledProcessError, OSError, ValueError):
        return False
    return True


def preflight(release: int, target: str, base: str, ref: str) -> None:
    if os.geteuid() != 0 or output(["hostname", "-s"]) != "tracker-dev":
        raise ReleaseError("Run as root on tracker-dev only")
    if git("branch", "--show-current") != "main":
        raise ReleaseError("DEV must be on local main")
    if git("status", "--porcelain"):
        raise ReleaseError("DEV checkout must be clean")
    if git("rev-parse", "HEAD") != target:
        raise ReleaseError("DEV installation does not match qualified target")
    if output(["systemctl", "is-active", "tracker"]) != "active":
        raise ReleaseError("DEV Tracker service is not active")

    log = ROOT / f"release-{release}-dev.log"
    secure_file(log, private=True)
    verified_log(log.read_text(encoding="utf-8"), target)

    run([
        "git", "-c", f"safe.directory={APP}", "-C", str(APP),
        "fetch", "origin", "main", f"refs/heads/{ref}:refs/remotes/origin/{ref}",
    ])
    main = git("rev-parse", "origin/main")
    allowed_648 = release == 648 and recovery_648_main_allowed(
        main, target, base
    )
    allowed_677 = release == 677 and recovery_677_main_allowed(
        main, target, base
    )
    allowed_705 = release == 705 and recovery_705_prod_lag_allowed(
        main, target, base
    )
    allowed_768 = release == 768 and recovery_768_main_allowed(
        main, target, base
    )
    if main not in (base, target) and not (
        allowed_648 or allowed_677 or allowed_705 or allowed_768
    ):
        raise ReleaseError(f"GitHub main changed unexpectedly: {main}")
    if allowed_648:
        print(f"PROD_RECOVERY_648_ANCESTOR_VERIFIED={main}", flush=True)
    if allowed_677:
        print(f"PROD_RECOVERY_677_ANCESTOR_VERIFIED={main}", flush=True)
    if allowed_705:
        print(f"PROD_CATCHUP_705_FROM_MAIN={main}", flush=True)
    if allowed_768:
        print(f"PROD_RECOVERY_768_PROMOTED_MAIN={main}", flush=True)
    if git("rev-parse", f"refs/remotes/origin/{ref}") != target:
        raise ReleaseError("Release branch differs from exact qualified commit")
    run([
        "git", "-c", f"safe.directory={APP}", "-C", str(APP),
        "merge-base", "--is-ancestor", base, target,
    ])
    if remote("hostname -s") != "tracker-prod":
        raise ReleaseError("SSH destination is not tracker-prod")
    prod_head = remote(
        "git -c safe.directory=/opt/tracker -C /opt/tracker rev-parse HEAD"
    )
    if prod_head not in (base, target):
        raise ReleaseError(f"Unexpected PROD installed commit: {prod_head}")
    if remote("systemctl is-active tracker") != "active":
        raise ReleaseError("PROD Tracker service is not active")

    secure_file(ROOT / "signing/dev-signing-private.pem", private=True)
    secure_file(ROOT / "dev-signing-public.pem")
    secure_file(APP / "scripts/tracker_prod_remote568.sh")
    print(f"DEV_QUALIFIED={target}", flush=True)
    print(f"PROD_INSTALLED={prod_head}", flush=True)
    print(f"GITHUB_MAIN={main}", flush=True)
    print("PREFLIGHT=PASSED", flush=True)


def sign_and_transfer(target: str) -> None:
    folder = ROOT / "approvals"
    if folder.is_symlink():
        raise ReleaseError("Unsafe approvals directory")
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    if folder.stat().st_uid != 0 or folder.stat().st_mode & 0o077:
        raise ReleaseError("Approval directory must be root-only")
    approval = folder / f"{target}.approval"
    signature = folder / f"{target}.sig"
    if approval.is_symlink() or signature.is_symlink():
        raise ReleaseError("Approval material must not be symlinked")
    approval.write_text(f"tracker-dev-qualified-v1\ncommit={target}\n",
                        encoding="utf-8")
    approval.chmod(0o600)
    run([
        "openssl", "pkeyutl", "-sign", "-rawin",
        "-inkey", str(ROOT / "signing/dev-signing-private.pem"),
        "-in", str(approval), "-out", str(signature),
    ])
    signature.chmod(0o600)
    run([
        "openssl", "pkeyutl", "-verify", "-pubin",
        "-inkey", str(ROOT / "dev-signing-public.pem"), "-rawin",
        "-in", str(approval), "-sigfile", str(signature),
    ])
    run([
        *SSH, "-n", PROD,
        'test "$(hostname -s)" = tracker-prod && '
        "install -d -o root -g root -m 700 /etc/tracker-release/approvals",
    ])
    run([*SCP, str(approval), str(signature),
         f"{PROD}:/etc/tracker-release/approvals/"])
    verified = remote(
        f"/usr/local/sbin/tracker-verify-dev-approval {target}"
    )
    if f"DEV_APPROVAL_VERIFIED={target}" not in verified.splitlines():
        raise ReleaseError("PROD did not verify the signed approval")
    print(f"PROD_APPROVAL_VERIFIED={target}", flush=True)


def promote(target: str, base: str) -> None:
    run(["git", "-c", f"safe.directory={APP}", "-C", str(APP),
         "fetch", "origin", "main"])
    main = git("rev-parse", "origin/main")
    if (main == base or recovery_648_main_allowed(main, target, base)
            or recovery_677_main_allowed(main, target, base)
            or recovery_705_prod_lag_allowed(main, target, base)
            or recovery_768_main_allowed(main, target, base)):
        # Ordinary fast-forward only. Never rewrite GitHub main history.
        run(["git", "-c", f"safe.directory={APP}", "-C", str(APP),
             "push", "origin", f"{target}:refs/heads/main"])
    elif main != target:
        raise ReleaseError("GitHub main moved during promotion")
    run(["git", "-c", f"safe.directory={APP}", "-C", str(APP),
         "fetch", "origin", "main"])
    if git("rev-parse", "origin/main") != target:
        raise ReleaseError("GitHub main was not promoted to the target")
    print(f"PROMOTED_COMMIT={target}", flush=True)


def deploy(release: int, target: str, base: str) -> None:
    script = APP / "scripts/tracker_prod_remote568.sh"
    secure_file(script)
    # The script is streamed over authenticated SSH from the exact-qualified
    # clean DEV checkout. It is not required to exist on older PROD code.
    run([*SSH, "-T", PROD, "bash", "-s", "--", base, target, str(release)],
        input_data=script.read_bytes())
    final = remote("git -c safe.directory=/opt/tracker "
                   "-C /opt/tracker rev-parse HEAD")
    if final != target or remote("systemctl is-active tracker") != "active":
        raise ReleaseError("PROD post-deployment verification failed")
    print(f"PROD_INSTALLED_COMMIT={target}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=int, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--prod-base", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument(
        "--execute", action="store_true",
        help="Sign, promote GitHub main and deploy to PROD after DEV review",
    )
    args = parser.parse_args(argv)
    promoted = False
    try:
        validate(args.release, args.target, args.prod_base, args.ref)
        preflight(args.release, args.target, args.prod_base, args.ref)
        if not args.execute:
            print("DRY_RUN=PASSED (no approval, push, or deployment performed)")
            print("After visual approval, rerun with --execute")
            return 0
        sign_and_transfer(args.target)
        promote(args.target, args.prod_base)
        promoted = True
        deploy(args.release, args.target, args.prod_base)
        print("DEV_CONTROLLED_RELEASE=SUCCESS")
        return 0
    except (ReleaseError, OSError, UnicodeError, subprocess.CalledProcessError) as exc:
        # Do not expose .env, credentials, or token material in diagnostics.
        print(f"RELEASE_ERROR={exc}", file=sys.stderr)
        if promoted:
            print("PROMOTED_BUT_PROD_NOT_VERIFIED=YES", file=sys.stderr)
            print("Rerun after investigating; do not assume PROD deployed.",
                  file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
