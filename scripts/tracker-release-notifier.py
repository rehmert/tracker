#!/usr/bin/env python3
"""Send minimal release-stage push notices from tracker-dev via ntfy.

Runs as an optional, non-blocking ExecStartPost of the existing DEV agent.
Only root-owned local configuration contains the unpredictable ntfy topic.
The remote ntfy service receives no raw log, database, patient information,
test inputs, paths, application environment variables, or Git credentials.

A failed push never turns a deployment into a success or blocks deployment.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib import request as urlrequest

APP = Path("/opt/tracker")
CONFIG = Path("/etc/tracker-release-notify.json")
STATE = Path("/var/lib/tracker-release-agent")
SENT = STATE / "push-last.json"
RECEIPT_REF = "refs/remotes/origin/tracker-release-receipts"
TOPIC = re.compile(r"trk-[a-f0-9]{48}\Z")
SHA = re.compile(r"[a-f0-9]{40}\Z")
REQ = re.compile(r"r[1-9][0-9]{0,5}-[a-z0-9]{8,20}\Z")
ALLOWED_ACTIONS = {"qualify", "dev_install", "prod_preflight", "prod_deploy"}
ALLOWED_STATUSES = {"passed", "failed", "blocked", "unknown"}


def notification(receipt: dict) -> tuple[str, str, str] | None:
    """Return a bounded, public-safe title/body/priority, never log content."""
    if not isinstance(receipt, dict):
        return None
    release = receipt.get("release")
    action = receipt.get("action")
    status = receipt.get("status")
    target = receipt.get("target")
    if (
        type(release) is not int or not 1 <= release <= 999999
        or action not in ALLOWED_ACTIONS
        or status not in ALLOWED_STATUSES
        or not isinstance(target, str) or not SHA.fullmatch(target)
        or not isinstance(receipt.get("request_id"), str)
        or not REQ.fullmatch(receipt["request_id"])
    ):
        return None

    if status == "passed":
        if action == "dev_install":
            return (
                f"Tracker {release} DEV ready",
                f"Release {release} ({target[:7]}) installed on DEV and ready for testing. "
                "The signed release receipt is in GitHub.",
                "default",
            )
        if action == "prod_deploy":
            return (
                f"Tracker {release} PROD deployed",
                f"Release {release} ({target[:7]}) successfully verified on PROD.",
                "default",
            )
        return None  # avoid noise from successful intermediate checks

    step = {
        "qualify": "qualification",
        "dev_install": "DEV installation",
        "prod_preflight": "PROD preflight",
        "prod_deploy": "PROD deployment",
    }[action]
    return (
        f"Tracker {release} needs attention",
        f"Release {release} {step} reported {status}. "
        "Review the sanitized GitHub receipt before retrying.",
        "high",
    )


def read_config() -> dict | None:
    if not CONFIG.exists():
        return None
    stat = CONFIG.lstat()
    if not CONFIG.is_file() or os.path.islink(CONFIG):
        raise ValueError("Unsafe notification configuration")
    if stat.st_uid != 0 or stat.st_mode & 0o077:
        raise ValueError("Notification configuration must be root-only")
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict) or set(data) != {"topic"}
        or not isinstance(data["topic"], str)
        or not TOPIC.fullmatch(data["topic"])
    ):
        raise ValueError("Invalid notification topic configuration")
    return data


def current_receipt() -> dict | None:
    try:
        run = subprocess.run(
            ["git", "-c", f"safe.directory={APP}", "-C", str(APP),
             "show", f"{RECEIPT_REF}:receipts/latest.json"],
            capture_output=True, check=False, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if run.returncode or len(run.stdout) > 32768:
        return None
    data = json.loads(run.stdout)
    return data if isinstance(data, dict) else None


def send(topic: str, title: str, body: str, priority: str) -> None:
    if not TOPIC.fullmatch(topic):
        raise ValueError("Unsafe notification topic")
    if priority not in {"default", "high"}:
        raise ValueError("Unexpected priority")
    if len(title) > 100 or len(body) > 300:
        raise ValueError("Notification too large")
    req = urlrequest.Request(
        "https://ntfy.sh/" + topic,
        data=body.encode("utf-8"),
        headers={
            "Content-Type": "text/plain; charset=utf-8",
            "Title": title,
            "Priority": priority,
            "Tags": "white_check_mark" if priority == "default" else "warning",
        },
        method="POST",
    )
    with urlrequest.urlopen(req, timeout=8) as response:
        if not 200 <= response.status < 300:
            raise ValueError("Push provider did not confirm delivery")


def last_sent_id() -> str | None:
    try:
        value = json.loads(SENT.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    return value.get("request_id") if isinstance(value, dict) else None


def store_sent(request_id: str) -> None:
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(prefix=".push-", dir=STATE)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"request_id": request_id}, stream)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, SENT)
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass


def run(test: bool = False) -> None:
    if os.geteuid() != 0 or os.uname().nodename.split(".")[0] != "tracker-dev":
        raise ValueError("Notifications can only run as root on tracker-dev")
    config = read_config()
    if config is None:
        print("TRACKER_PUSH_NOT_CONFIGURED=SKIPPED", flush=True)
        return
    if test:
        send(config["topic"], "Tracker notifications enabled",
             "Your tracker-dev release push notifications are configured.", "default")
        print("TRACKER_PUSH_TEST=SENT", flush=True)
        return
    receipt = current_receipt()
    if receipt is None:
        return
    notice = notification(receipt)
    if notice is None:
        return
    request_id = receipt["request_id"]
    if last_sent_id() == request_id:
        return
    send(config["topic"], *notice)
    store_sent(request_id)
    print(f"TRACKER_PUSH_SENT={request_id}", flush=True)


if __name__ == "__main__":
    try:
        run(test=(len(sys.argv) == 2 and sys.argv[1] == "--test"))
    except Exception as exc:
        # Notification delivery is advisory only; never alter the authoritative
        # release result, or leak HTTP response body/token into the journal.
        print(f"TRACKER_PUSH_ERROR={type(exc).__name__}", file=sys.stderr)
        raise SystemExit(0)
