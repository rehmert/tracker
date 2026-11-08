"""Isolated fixtures and HTTP helpers for Release 440 secondary regression gates.

Only the two Release 440 test modules import this file. These functions
remain test-only and never change production authentication or gateway logic.
"""
import re
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, session_auth385 as auth
from app.secondary_preview430 import preview_app
from app.user_accounts427 import stage_secondary_account427
from app.user_bootstrap426 import initialize_staged_workspace426

FEATURES = (
    ("TRACKER_SECONDARY_VITAL_WRITES433", "vitals", "/secondary/vitals/new"),
    ("TRACKER_SECONDARY_DOSE_WRITES434", "doses", "/secondary/doses/new"),
    ("TRACKER_SECONDARY_INVENTORY_WRITES435", "inventory",
     "/secondary/inventory/compounds"),
    ("TRACKER_SECONDARY_RECONSTITUTION_WRITES436", "reconstitution",
     "/secondary/reconstitution"),
    ("TRACKER_SECONDARY_VIAL_CORRECTIONS437", "vial_corrections",
     "/secondary/reconcile/correct"),
    ("TRACKER_SECONDARY_SUPPLY_WRITES438", "supply_intake",
     "/secondary/supplies"),
    ("TRACKER_SECONDARY_SUPPLY_USE439", "supply_use",
     "/secondary/supplies/use"),
)


@pytest.fixture
def browser(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "instance_label", lambda: "DEV")
    monkeypatch.setenv("TRACKER_SECONDARY_PREVIEW430", "1")
    monkeypatch.delenv("TRACKER_SECONDARY_LOCKDOWN440", raising=False)
    for flag, _, _ in FEATURES:
        monkeypatch.setenv(flag, "1")

    auth.bootstrap("operator", "administrator-secure-password-440")
    (tmp_path / auth.FLAG).write_text("DEV enabled")

    for uid in (2, 3):
        initialize_staged_workspace426(uid, tmp_path)
        stage_secondary_account427(
            uid, f"member-{uid}", f"secondary-secure-password-{uid}-440",
        )

    host = FastAPI()
    host.mount("/secondary", preview_app)
    with TestClient(host, base_url="https://tracker.test") as client:
        yield client, tmp_path


def _hidden(html, field):
    found = re.search(
        rf'name="{re.escape(field)}"\s+value="([^"]+)"',
        html,
    )
    assert found, f"Hidden field {field} not found"
    return found.group(1)


def _login(client, uid):
    page = client.get("/secondary/login")
    assert page.status_code == 200
    result = client.post(
        "/secondary/login", data={
            "username": f"member-{uid}",
            "password": f"secondary-secure-password-{uid}-440",
            "csrf_token": _hidden(page.text, "csrf_token"),
        },
        follow_redirects=False,
    )
    assert result.status_code == 303


def _post_form(client, page_path, action, fields):
    response = client.get(page_path)
    assert response.status_code == 200, (
        page_path, response.status_code, response.text[:200]
    )
    pattern = (
        r'<form\b[^>]*\baction="' + re.escape(action)
        + r'"[^>]*>(.*?)</form>'
    )
    found = re.search(pattern, response.text, flags=re.S)
    assert found, f"Form action {action} not found on {page_path}"
    inner = found.group(1)
    data = {
        "csrf_token": _hidden(inner, "csrf_token"),
        "submission_token": _hidden(inner, "submission_token"),
        **fields,
    }
    result = client.post(action, data=data, follow_redirects=False)
    assert result.status_code == 303, (
        action, result.status_code, result.text[:250]
    )
    return result


def _row(html, feature):
    found = re.search(
        rf'<tr data-feature="{re.escape(feature)}">(.*?)</tr>',
        html, flags=re.S,
    )
    assert found, f"Missing capability {feature}"
    return found.group(1)


def _counts(root, uid):
    path = root / "users" / str(uid) / "tracker.db"
    with sqlite3.connect(path) as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "compounds", "vials", "preparation_events", "dose_logs",
                "vital_readings", "supplies", "supply_usages",
                "preparation_supplies", "change_audit",
            )
        }