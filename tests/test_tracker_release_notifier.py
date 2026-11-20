"""Offline tests for minimal, root-owned, best-effort Tracker push alerts."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
from unittest.mock import patch
from urllib.error import URLError

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/tracker-release-notifier.py"
spec = importlib.util.spec_from_file_location("tracker_release_notifier", SOURCE)
notifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notifier)

TARGET = "7c662491c3a233b3df60842bbaeaa2dfbc995f06"
TOPIC = "trk-" + "a" * 48
REQ = "r711-925bf13e6d74"


def receipt(action="dev_install", status="passed", **changed):
    value = {
        "schema": 1, "release": 711, "action": action, "status": status,
        "target": TARGET, "request_id": REQ, "failure_category": None,
        "failed_tests": [], "test_counts": ["68 passed, 1 warning"],
    }
    value.update(changed)
    return value


def test_dev_install_triggers_dev_ready_push_with_only_public_metadata():
    title, body, priority = notifier.notification(
        receipt(failure_category="DO_NOT_FORWARD", medical_data="secret")
    )
    assert "DEV ready" in title and "711" in title
    assert "7c66249" in body
    assert "secret" not in repr((title, body, priority))
    assert "DO_NOT_FORWARD" not in repr((title, body, priority))
    assert "68 passed" not in body
    assert priority == "default"


def test_intermediate_passes_do_not_send_notification():
    for action in ("qualify", "prod_preflight"):
        assert notifier.notification(receipt(action=action)) is None


@pytest.mark.parametrize("action", ("qualify", "dev_install", "prod_preflight", "prod_deploy"))
@pytest.mark.parametrize("status", ("failed", "blocked", "unknown"))
def test_nonpassed_stages_raise_bounded_alert(action, status):
    title, body, priority = notifier.notification(
        receipt(action=action, status=status)
    )
    assert "needs attention" in title
    assert status in body and priority == "high"


@pytest.mark.parametrize("invalid", (
    {"release": True}, {"release": "711"}, {"release": 0},
    {"action": "arbitrary-command"}, {"status": "approved"},
    {"target": "not-a-commit"}, {"target": "a" * 40 + "x"},
    {"request_id": "../secrets"}, {"request_id": 7},
))
def test_malformed_receipt_is_silently_ignored(invalid):
    assert notifier.notification(receipt(**invalid)) is None


def test_send_posts_only_minimal_body_to_fixed_https_provider():
    outgoing = []
    class Response:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None

    def send(req, timeout):
        outgoing.append((req, timeout))
        return Response()

    with patch.object(notifier.urlrequest, "urlopen", side_effect=send):
        notifier.send(TOPIC, "Tracker DEV ready", "Release 711 installed.", "default")
    assert len(outgoing) == 1
    req, timeout = outgoing[0]
    assert req.full_url == "https://ntfy.sh/" + TOPIC
    assert req.get_method() == "POST" and timeout <= 8
    assert req.data == b"Release 711 installed."
    assert req.headers["Title"] == "Tracker DEV ready"
    with pytest.raises(ValueError):
        notifier.send("malicious/path", "A", "B", "high")
    with pytest.raises(ValueError):
        notifier.send(TOPIC, "A", "B", "critical")


def test_dedupe_receipt_by_request_id_and_retries_delivery_on_failure(tmp_path):
    config = tmp_path / "notify.json"
    config.write_text(json.dumps({"topic": TOPIC}))
    os.chmod(config, 0o600)
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    os.chmod(state, 0o700)
    entry = receipt()
    with patch.object(notifier, "CONFIG", config), \
         patch.object(notifier, "STATE", state), \
         patch.object(notifier, "SENT", state / "push-last.json"), \
         patch.object(notifier, "current_receipt", return_value=entry), \
         patch.object(notifier.os, "geteuid", return_value=0), \
         patch.object(notifier.os, "uname") as uname:
        uname.return_value.nodename = "tracker-dev"
        with patch.object(notifier, "send", side_effect=URLError("offline")):
            with pytest.raises(URLError):
                notifier.run()
            assert notifier.last_sent_id() is None
        with patch.object(notifier, "send") as send:
            notifier.run()
            notifier.run()
            assert send.call_count == 1
            assert notifier.last_sent_id() == REQ


def test_unconfigured_notifier_skips_without_sending(tmp_path):
    with patch.object(notifier, "CONFIG", tmp_path / "missing"), \
         patch.object(notifier.os, "geteuid", return_value=0), \
         patch.object(notifier.os, "uname") as uname, \
         patch.object(notifier, "send") as send:
        uname.return_value.nodename = "tracker-dev"
        notifier.run()
        assert not send.called


def test_ops_installer_runs_after_agent_and_keeps_secret_local():
    source = (ROOT / "scripts/tracker-release-agent-install.sh").read_text()
    assert "ExecStartPost=/usr/bin/python3 -I /usr/local/sbin/tracker-release-notifier.py" in source
    assert "secrets.token_hex(24)" in source
    assert "os.O_EXCL" in source
    assert "NOTIFY_CONFIG=/etc/tracker-release-notify.json" in source
    assert "stat -c '%a'" in source
    assert "chmod 777" not in source
    assert "TRACKER_RELEASE_AGENT_PROD=UNTOUCHED" in source
    assert "systemctl is-active --quiet tracker-release-agent.service" in source
    assert "Tracker service must be active" in source
    result = subprocess.run(["bash", "-n", str(ROOT / "scripts/tracker-release-agent-install.sh")],
                            capture_output=True)
    assert result.returncode == 0


def test_notifier_contains_no_chat_api_token_or_webhook_secret():
    code = SOURCE.read_text()
    assert "https://ntfy.sh/" in code
    assert "os.environ" not in code
    assert "AGENT_ACCESS_TOKEN" not in code
    assert "chatgpt.com" not in code
    assert "print(config" not in code
    assert re.search(r"except Exception as exc:", code)
    assert 'raise SystemExit(0)' in code  # best-effort never blocks releases
