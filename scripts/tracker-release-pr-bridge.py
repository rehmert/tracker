#!/usr/bin/env python3
"""Bridge one validated, published DEV release receipt to one GitHub PR event.

The stable open release-event PR is never mergeable as a code release:
a one-file marker on tracker-release-events is pushed after the receipt is
already committed on tracker-release-receipts. Its PR synchronize event can
wake a configured GitHub-event Work task without polling.

This is a best-effort root-owned systemd ExecStartPost hook. A failure cannot
alter the authoritative release receipt or deploy any software.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

APP = Path("/opt/tracker")
EVENT_BRANCH = "tracker-release-events"
RECEIPT_BRANCH = "tracker-release-receipts"
EVENT_REF = "refs/remotes/origin/" + EVENT_BRANCH
RECEIPT_REF = "refs/remotes/origin/" + RECEIPT_BRANCH
EVENT_PATH = "events/latest.json"
RECEIPT_LATEST = "receipts/latest.json"
SHA = re.compile(r"[0-9a-f]{40}\Z")
REQUEST_ID = re.compile(r"r[1-9][0-9]{0,5}-[a-z0-9]{8,20}\Z")
BRANCH = re.compile(r"release/([1-9][0-9]{0,5})-[a-z0-9-]+\Z")
ACTIONS = {"qualify", "dev_install", "prod_preflight", "prod_deploy"}
STATUSES = {"passed", "failed", "blocked", "unknown"}


class BridgeError(Exception):
    pass


def git(*args: str, input_bytes: bytes | None = None, env: dict | None = None) -> bytes:
    process = subprocess.run(
        ["git", "-c", f"safe.directory={APP}", "-C", str(APP), *args],
        input=input_bytes, capture_output=True, env=env, check=False, timeout=90,
    )
    if process.returncode:
        # Do not print full git stderr: remote URLs can include credentials.
        raise BridgeError("Git operation failed: " + args[0])
    return process.stdout


def fetch(branch: str) -> None:
    if branch not in (EVENT_BRANCH, RECEIPT_BRANCH):
        raise BridgeError("Unapproved GitHub branch")
    git("fetch", "--no-tags", "origin",
        f"refs/heads/{branch}:refs/remotes/origin/{branch}")


def show(ref: str, path: str) -> bytes | None:
    if ref not in (EVENT_REF, RECEIPT_REF):
        raise BridgeError("Unapproved GitHub reference")
    if path != EVENT_PATH and path != RECEIPT_LATEST and not (
        ref == RECEIPT_REF
        and re.fullmatch(r"receipts/r[1-9][0-9]{0,5}-[a-z0-9]{8,20}[.]json", path)
    ):
        raise BridgeError("Unapproved read path")
    run = subprocess.run(
        ["git", "-c", f"safe.directory={APP}", "-C", str(APP),
         "show", f"{ref}:{path}"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=20,
    )
    if run.returncode:
        return None
    if len(run.stdout) > 32768:
        raise BridgeError("Read data exceeds expected size")
    return run.stdout


def json_object(data: bytes | None) -> dict | None:
    if data is None:
        return None
    value = json.loads(data)
    if not isinstance(value, dict):
        raise BridgeError("Expected a JSON object")
    return value


def sanitized_event(receipt: dict) -> dict:
    """Constrain the event to a tiny public-safe receipt pointer.

    Do not copy any user-entered notes, test names, log lines, errors,
    environment settings, or token values from the receipt.
    """
    req = receipt.get("request_id")
    release = receipt.get("release")
    action = receipt.get("action")
    status = receipt.get("status")
    target = receipt.get("target")
    ref = receipt.get("ref")
    if (
        not isinstance(req, str) or not REQUEST_ID.fullmatch(req)
        or type(release) is not int or not 1 <= release <= 999999
        or action not in ACTIONS
        or status not in STATUSES
        or not isinstance(target, str) or not SHA.fullmatch(target)
        or not isinstance(ref, str)
    ):
        raise BridgeError("Invalid release receipt metadata")
    match = BRANCH.fullmatch(ref)
    if not match or int(match.group(1)) != release:
        raise BridgeError("Release branch identity mismatch")
    return {
        "schema": 1,
        "event_type": "tracker-release-receipt",
        "request_id": req,
        "release": release,
        "action": action,
        "status": status,
        "target": target,
        "receipt_branch": RECEIPT_BRANCH,
        "receipt_path": f"receipts/{req}.json",
    }


def current_receipt() -> dict:
    fetch(RECEIPT_BRANCH)
    latest_bytes = show(RECEIPT_REF, RECEIPT_LATEST)
    latest = json_object(latest_bytes)
    if latest is None:
        raise BridgeError("No published release receipt")
    event = sanitized_event(latest)
    individual = show(RECEIPT_REF, event["receipt_path"])
    if individual is None or json_object(individual) != latest:
        raise BridgeError("Latest receipt and immutable per-request receipt disagree")
    return event


def publish_event(event: dict) -> bool:
    """Update only the PR marker in an isolated Git index; never installed main."""
    content = (json.dumps(event, sort_keys=True, indent=2) + "\n").encode("utf-8")
    for _attempt in range(3):
        fetch(EVENT_BRANCH)
        existing = json_object(show(EVENT_REF, EVENT_PATH))
        if existing is not None and existing.get("request_id") == event["request_id"]:
            if existing != event:
                raise BridgeError("Same request ID has conflicting event metadata")
            return False
        parent = git("rev-parse", EVENT_REF).decode().strip()
        if not SHA.fullmatch(parent):
            raise BridgeError("Invalid event branch head")
        with tempfile.TemporaryDirectory(prefix="tracker-pr-bridge-") as folder:
            env = os.environ.copy()
            env["GIT_INDEX_FILE"] = str(Path(folder) / "index")
            env["GIT_AUTHOR_NAME"] = "Tracker Release Event Bridge"
            env["GIT_AUTHOR_EMAIL"] = "tracker-release-event@localhost"
            env["GIT_COMMITTER_NAME"] = env["GIT_AUTHOR_NAME"]
            env["GIT_COMMITTER_EMAIL"] = env["GIT_AUTHOR_EMAIL"]
            git("read-tree", parent, env=env)
            blob = git("hash-object", "-w", "--stdin",
                       input_bytes=content, env=env).decode().strip()
            git("update-index", "--add", "--cacheinfo",
                f"100644,{blob},{EVENT_PATH}", env=env)
            tree = git("write-tree", env=env).decode().strip()
            commit = git(
                "commit-tree", tree, "-p", parent,
                "-m", f"Tracker release-event r{event['release']}: {event['action']} {event['status']}",
                env=env,
            ).decode().strip()
        push = subprocess.run(
            ["git", "-c", f"safe.directory={APP}", "-C", str(APP),
             "push", "origin", f"{commit}:refs/heads/{EVENT_BRANCH}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=90,
        )
        if push.returncode == 0:
            print("TRACKER_RELEASE_PR_EVENT_PUBLISHED=" + event["request_id"], flush=True)
            return True
        time.sleep(1)
    raise BridgeError("Could not update release-event PR branch")


def run(*, check_only: bool = False) -> None:
    if os.geteuid() != 0 or os.uname().nodename.split(".")[0] != "tracker-dev":
        raise BridgeError("Release-event bridge must run as root on tracker-dev")
    event = current_receipt()
    if check_only:
        fetch(EVENT_BRANCH)
        print("TRACKER_RELEASE_PR_BRIDGE_PREFLIGHT=PASSED", flush=True)
        return
    publish_event(event)


if __name__ == "__main__":
    check_only = len(sys.argv) == 2 and sys.argv[1] == "--check"
    try:
        run(check_only=check_only)
    except Exception as exc:
        # Required only for the explicit operator preflight. An event delivery
        # failure cannot change a finished release's result/status/exit code.
        print("TRACKER_RELEASE_PR_BRIDGE_ERROR=" + type(exc).__name__, file=sys.stderr)
        raise SystemExit(1 if check_only else 0)
