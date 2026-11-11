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
    """Check literal runner markers without the exact-heading whitespace bug."""
    lines = content.splitlines()
    for marker in QUALIFICATION:
        if marker not in lines:
            raise ReleaseError(f"Missing DEV qualification marker: {marker}")
    if not any("TRACKER RELEASE DEPLOYMENT SUCCESS" in line for line in lines):
        raise ReleaseError("Missing guarded deployment success heading")
    statuses = [line for line in lines if line.startswith("EXIT_STATUS=")]
    if not statuses or statuses[-1] != "EXIT_STATUS=0":
        raise ReleaseError("Last DEV deployment status is not zero")
    exact = f"DEV_QUALIFIED_COMMIT={target}"
    if exact not in lines:
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
    if main not in (base, target):
        raise ReleaseError(f"GitHub main changed unexpectedly: {main}")
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
    if main == base:
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
