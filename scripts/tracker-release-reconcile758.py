#!/usr/bin/env python3
"""One-time, fail-closed DEV controller reconciliation: installed 757 -> qualify 758.

Does not execute a PROD command, change application data, rewrite an immutable
receipt, or skip isolated qualification. Must run on tracker-dev as root from
the exact Release 758 candidate object; the installed agent remains trusted.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile

APP = Path("/opt/tracker")
STATE = Path("/var/lib/tracker-release-agent")
LOGS = Path("/var/log/tracker-release-agent")
AGENT = Path("/usr/local/sbin/tracker-release-agent.py")
BASE = "90b297fc07c950d5a44a0bf8fe7d4beabfd8b30f"
OLD_ID = "r751-f495d0f9686a"
OLD_TARGET = "f495d0f9686a24403f874f932e34a5039a186dce"
OLD_BASE = "2ff72f49449306ea5b11dc9c861d0cac5973131e"
OLD_REF = "release/751-strict-csrf-dev-rollout"
NEW_REF = "release/758-vial-label-dose-markings"
QUEUE = "refs/remotes/origin/tracker-release-requests"
RECEIPTS = "refs/remotes/origin/tracker-release-receipts"
HISTORY = STATE / "control-history745.json"
BACKUP = STATE / "control-history-before758.json"
LOCAL_AUDIT = STATE / "reconciliation758.json"
TIMER = "tracker-release-agent.timer"
SERVICE = "tracker-release-agent.service"
SHA = re.compile(r"[0-9a-f]{40}\Z")


class Blocked(RuntimeError):
    pass


def require(value, reason: str):
    if not value:
        raise Blocked(reason)


def shell(*args: str, input_data: bytes | None = None,
          env: dict | None = None, timeout: int = 90) -> bytes:
    run = subprocess.run(args, input=input_data, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, env=env, timeout=timeout,
                         check=False)
    if run.returncode:
        raise Blocked(f"Command failed: {args[0]} {args[1] if len(args)>1 else ''} (exit {run.returncode})")
    return run.stdout


def git(*args: str, input_data: bytes | None = None, env: dict | None = None) -> bytes:
    return shell("git", "-c", f"safe.directory={APP}", "-C", str(APP), *args,
                 input_data=input_data, env=env)


def show(ref: str, path: str) -> bytes:
    return git("show", f"{ref}:{path}")


def read_git_json(ref: str, path: str) -> dict:
    value = json.loads(show(ref, path))
    require(isinstance(value, dict), f"Non-object GitHub JSON: {path}")
    return value


def atomic_json(path: Path, value: dict):
    data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    fd, name = tempfile.mkstemp(prefix=".reconcile758-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(name)


def candidate(target: str) -> dict:
    require(isinstance(target, str) and SHA.fullmatch(target),
            "Candidate must be a full pinned SHA")
    require(target != BASE, "Candidate cannot be installed base")
    return {"schema": 1, "request_id": "r758-" + target[:12],
            "action": "qualify", "release": 758, "target": target,
            "base": BASE, "ref": NEW_REF, "previous_request_id": None}


def validate_stale(command: dict, receipt: dict):
    expected = {"schema": 1, "request_id": OLD_ID, "action": "qualify",
                "release": 751, "target": OLD_TARGET, "base": OLD_BASE,
                "ref": OLD_REF, "previous_request_id": None}
    require(command == expected, "Queue is not the exact stale 751 request")
    for field, value in expected.items():
        require(receipt.get(field) == value, "Immutable 751 receipt mismatch: " + field)
    require(receipt.get("status") == "failed" and receipt.get("exit_code") == 1
            and receipt.get("failure_category") == "GateError"
            and receipt.get("markers") == []
            and receipt.get("test_counts") == []
            and receipt.get("failed_tests") == [],
            "751 was not the recorded pre-execution gate failure")


def verify_host(target: str, script: Path):
    require(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "tracker-dev",
            "Root on tracker-dev required")
    require(APP.is_dir() and not APP.is_symlink(), "Unsafe installed APP")
    require(STATE.is_dir() and not STATE.is_symlink()
            and STATE.stat().st_uid == 0
            and STATE.stat().st_mode & 0o077 == 0, "Unsafe controller state")
    require(LOGS.is_dir() and not LOGS.is_symlink(), "Missing controller log directory")
    require(AGENT.is_file() and not AGENT.is_symlink()
            and AGENT.stat().st_uid == 0
            and AGENT.stat().st_mode & 0o077 == 0, "Unsafe installed controller")
    require(git("branch", "--show-current").decode().strip() == "main"
            and git("rev-parse", "HEAD").decode().strip() == BASE
            and not git("status", "--porcelain"),
            "Installed DEV must be clean Release 757 main")
    shell("systemctl", "is-active", "--quiet", "tracker.service")
    require(git("hash-object", str(AGENT)).decode().strip() ==
            git("rev-parse", BASE + ":scripts/tracker-release-agent745.py").decode().strip(),
            "Trusted host agent differs from installed source")
    require(git("hash-object", str(script)).decode().strip() ==
            git("rev-parse", target + ":scripts/tracker-release-reconcile758.py").decode().strip(),
            "Recovery script does not match pinned source object")
    raw = (LOGS / (OLD_ID + ".log"))
    require(raw.is_file() and not raw.is_symlink()
            and "LOCAL_STAGE_ERROR=Installed DEV commit does not match required source"
            in raw.read_text(errors="replace"), "No matching local 751 gate evidence")


def verify_history(parent_ref: str):
    require(HISTORY.is_file() and not HISTORY.is_symlink(), "Missing controller history")
    old = json.loads(HISTORY.read_text())
    anchor = old.get("ref")
    require(isinstance(anchor, str) and SHA.fullmatch(anchor),
            "Invalid controller history anchor")
    git("merge-base", "--is-ancestor", anchor, parent_ref)
    # Independently verify every intervening command transition using the
    # exact source of the currently installed, hash-checked agent.
    spec = importlib.util.spec_from_file_location("tracker_agent745_758", AGENT)
    require(spec is not None and spec.loader is not None, "Agent import failure")
    agent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agent)
    commits = git("rev-list", "--reverse", f"{anchor}..{parent_ref}").decode().splitlines()
    require(len(commits) <= 128, "Too many unverified controller transitions")
    old_ref = anchor
    for new_ref in commits:
        previous = read_git_json(old_ref, "control/current.json")
        following = read_git_json(new_ref, "control/current.json")
        agent.validate_command(previous)
        agent.validate_command(following)
        if previous != following:
            receipt = read_git_json(RECEIPTS, "receipts/" + previous["request_id"] + ".json")
            agent.validate_control_transition(previous, following, receipt)
        old_ref = new_ref
    return anchor


def commit_request(parent: str, current: dict, target: str) -> str:
    new = candidate(target)
    audit = {"schema": 1, "scope": "DEV_ONLY",
             "kind": "controller_reconciliation_not_release_receipt",
             "reason": "DEV installed Release 757 while queue retained failed 751",
             "previous_request_id": OLD_ID,
             "previous_queue_ref": parent,
             "verified_installed_dev": BASE,
             "new_request_id": new["request_id"],
             "new_target": target,
             "notes": "Old receipt preserved; qualification required before DEV installation"}
    with tempfile.TemporaryDirectory(prefix="tracker758-index-", dir=STATE) as d:
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = str(Path(d) / "index")
        env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = "Tracker DEV Recovery"
        env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = "tracker-dev-recovery@localhost"
        git("read-tree", parent, env=env)
        for path, payload in (
            ("control/current.json", new),
            ("control/reconciliation758.json", audit),
        ):
            body = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode()
            blob = git("hash-object", "-w", "--stdin", input_data=body, env=env).decode().strip()
            git("update-index", "--add", "--cacheinfo",
                f"100644,{blob},{path}", env=env)
        tree = git("write-tree", env=env).decode().strip()
        new_commit = git("commit-tree", tree, "-p", parent,
                         "-m", "DEV-only controller reconciliation: installed 757 to 758 qualification",
                         env=env).decode().strip()
    # No force: fast-forward push is an expected-parent CAS. A concurrent
    # change will reject this push instead of overwriting an outstanding stage.
    git("push", "origin", f"{new_commit}:refs/heads/tracker-release-requests")
    git("fetch", "--no-tags", "origin",
        "refs/heads/tracker-release-requests:refs/remotes/origin/tracker-release-requests")
    require(git("rev-parse", QUEUE).decode().strip() == new_commit,
            "Queue ref changed after recovery push")
    return new_commit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="Full pinned Release 758 source SHA")
    parser.add_argument("--apply", action="store_true",
                        help="Explicit one-time controller reconciliation")
    args = parser.parse_args()
    require(args.apply, "--apply is required")
    target = args.target
    new = candidate(target)
    require(os.geteuid() == 0 and socket.gethostname().split(".")[0] == "tracker-dev",
            "Root on tracker-dev required")
    require(STATE.is_dir(), "Controller state is missing")
    # Block new timer invocations while reconciling. Do not kill a running
    # service because its stage might have begun changing installed files.
    active = shell("systemctl", "show", "--property=ActiveState",
                   "--value", SERVICE).decode().strip()
    require(active in ("inactive", "failed"), "Agent stage is active; do not interrupt")
    timer_loaded = shell("systemctl", "show", "--property=LoadState",
                         "--value", TIMER).decode().strip()
    require(timer_loaded == "loaded", "Expected agent timer is unavailable")
    timer_was_active = subprocess.run(
        ["systemctl", "is-active", "--quiet", TIMER], check=False).returncode == 0
    shell("systemctl", "stop", TIMER)
    remote_changed = False
    anchored = False
    try:
        with (STATE / "lock").open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for ref in ("tracker-release-requests", "tracker-release-receipts",
                        "release/757-calendar-vial-syringe-units", NEW_REF):
                git("fetch", "--no-tags", "origin",
                    f"refs/heads/{ref}:refs/remotes/origin/{ref}")
            require(git("rev-parse", "refs/remotes/origin/release/757-calendar-vial-syringe-units").decode().strip() == BASE,
                    "Release 757 branch no longer equals installed baseline")
            require(git("rev-parse", "refs/remotes/origin/" + NEW_REF).decode().strip() == target,
                    "Release 758 branch moved; refresh pinned target")
            git("merge-base", "--is-ancestor", BASE, target)
            verify_host(target, Path(__file__))
            require(not (STATE / "pending.json").exists(), "Unpublished pending stage exists")
            require(not (STATE / (new["request_id"] + ".started")).exists(),
                    "Release 758 request was already started")
            require(not (STATE / (new["request_id"] + ".log")).exists(),
                    "Release 758 request already has a private stage log")
            receipt = read_git_json(RECEIPTS, "receipts/latest.json")
            stale_receipt = read_git_json(RECEIPTS, "receipts/" + OLD_ID + ".json")
            require(receipt == stale_receipt, "Latest receipt not the immutable 751 failure")
            require(receipt["request_id"] == OLD_ID, "Latest stage no longer stale 751")
            # A published receipt for the new request must never be rerun.
            check = subprocess.run(
                ["git", "-c", f"safe.directory={APP}", "-C", str(APP),
                 "cat-file", "-e", f"{RECEIPTS}:receipts/{new['request_id']}.json"],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            require(check.returncode != 0, "New request already has immutable receipt")
            parent = git("rev-parse", QUEUE).decode().strip()
            existing = read_git_json(QUEUE, "control/current.json")
            if existing == new:
                # Idempotent recovery if the fast-forward push succeeded but
                # a local interruption occurred before the anchor update.
                audit = read_git_json(QUEUE, "control/reconciliation758.json")
                require(audit.get("kind") == "controller_reconciliation_not_release_receipt"
                        and audit.get("previous_request_id") == OLD_ID
                        and audit.get("verified_installed_dev") == BASE
                        and audit.get("new_request_id") == new["request_id"]
                        and audit.get("new_target") == target,
                        "Existing queued reconciliation cannot be authenticated")
                previous_parent = audit["previous_queue_ref"]
                require(git("rev-parse", parent + "^").decode().strip() == previous_parent,
                        "Unexpected reconciliation ancestry")
                verify_history(previous_parent)
                new_head = parent
            else:
                validate_stale(existing, receipt)
                verify_history(parent)
                new_head = commit_request(parent, existing, target)
                remote_changed = True
            # Verify the immutable last receipt did not change in the interim.
            git("fetch", "--no-tags", "origin",
                "refs/heads/tracker-release-receipts:refs/remotes/origin/tracker-release-receipts")
            require(read_git_json(RECEIPTS, "receipts/latest.json") == receipt,
                    "Receipt changed during reconciliation")
            current_history = json.loads(HISTORY.read_text())
            if current_history.get("ref") != new_head:
                if not BACKUP.exists():
                    atomic_json(BACKUP, current_history)
                else:
                    require(json.loads(BACKUP.read_text()) == current_history,
                            "Previous controller-history backup mismatch")
                atomic_json(LOCAL_AUDIT, {
                    "schema": 1, "scope": "DEV_ONLY", "old_controller_anchor": current_history["ref"],
                    "previous_queue_ref": parent if remote_changed else previous_parent,
                    "new_queue_ref": new_head, "failed_receipt": OLD_ID,
                    "verified_installed_dev": BASE, "queued_758_request": new["request_id"],
                    "no_prod_authorization": True,
                })
                atomic_json(HISTORY, {"ref": new_head})
            require(json.loads(HISTORY.read_text()) == {"ref": new_head},
                    "Controller history did not adopt verified recovery ref")
            anchored = True
        print("RELEASE_758_CONTROL_RECONCILIATION=PASSED", flush=True)
        print("RELEASE_758_QUALIFICATION_REQUEST=" + new["request_id"], flush=True)
        print("RELEASE_758_QUALIFICATION_SHA=" + target, flush=True)
    finally:
        if timer_was_active and (anchored or not remote_changed):
            shell("systemctl", "start", TIMER)
        elif remote_changed and not anchored:
            print("RELEASE_758_BLOCKED=Queue changed before local history reset; timer remains stopped", flush=True)
    if anchored:
        shell("systemctl", "start", "--no-block", SERVICE)
        print("RELEASE_758_DEV_AGENT=START_REQUESTED", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Blocked, OSError, ValueError, json.JSONDecodeError,
            subprocess.TimeoutExpired, BlockingIOError) as exc:
        print("RELEASE_758_RECONCILIATION_BLOCKED=" + str(exc), flush=True)
        raise SystemExit(2)
