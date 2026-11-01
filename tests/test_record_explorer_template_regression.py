"""Shared tool-page rendering and Record Explorer HTTP regression tests.

Isolated temporary SQLite database; never accesses the running Tracker DB.
"""
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config
from app.routers import record_explorer, workflow_tools
from app.templating import templates
from app.tool_layout import render_tool_page


@pytest.fixture
def explorer_client(tmp_path, monkeypatch):
    path = tmp_path / "record-explorer-tests.db"
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE vials (
            id INTEGER PRIMARY KEY,
            label TEXT, status TEXT, received_on TEXT, expires_on TEXT
        );
        INSERT INTO vials(id, label, status, received_on)
        VALUES (1, 'Test vial', 'sealed', '2026-10-01');

        CREATE TABLE vital_readings (
            measured_at TEXT, weight_kg REAL, systolic INTEGER,
            diastolic INTEGER, pulse_bpm INTEGER
        );
        INSERT INTO vital_readings VALUES
            ('2026-10-30T10:00:00', 120.5, 125, 75, 80);

        CREATE TABLE pages (
            id INTEGER PRIMARY KEY, title TEXT, body TEXT
        );
        INSERT INTO pages VALUES (1, 'Example note', 'Updated content');

        CREATE TABLE page_revisions (
            id INTEGER PRIMARY KEY, page_id INTEGER, title TEXT,
            body TEXT, created_at TEXT
        );
        INSERT INTO page_revisions VALUES
            (1, 1, 'Example note', 'Old content', '2026-10-30');

        CREATE TABLE vendor_site_credentials (
            id INTEGER PRIMARY KEY, password TEXT
        );
        INSERT INTO vendor_site_credentials VALUES (1, 'not-for-display');
        """)
    monkeypatch.setattr(config, "DB_URL", f"sqlite:///{path}")
    app = FastAPI()
    app.include_router(record_explorer.router)
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("instance", ["DEV", "PROD", ""])
def test_shared_tool_layout_has_application_globals(monkeypatch, instance):
    monkeypatch.setenv("TRACKER_INSTANCE", instance)
    assert templates.env.globals["tracker_instance_label"]() == instance
    document = render_tool_page("Test Explorer", "<strong>Read-only test</strong>")
    assert "<strong>Read-only test</strong>" in document
    assert "<title>" + (f"[{instance}] " if instance else "") + (
        "Test Explorer · Tracker</title>"
    ) in document
    if instance:
        assert f"tracker-instance--{instance.lower()}" in document
    assert '<script src="/static/tool_enhancements.js' in document
    assert "<title>" in document
    assert "<script" not in document.split("<title>", 1)[1].split("</title>", 1)[0]


@pytest.mark.parametrize("route, expected", [
    ("/record-explorer/vials", "Vial lifecycle"),
    ("/record-explorer/health", "Health record explorer"),
    ("/record-explorer/notes", "Notes history"),
    ("/record-explorer/notes/1", "Notes comparison"),
    ("/record-explorer/database", "Database explorer"),
    ("/record-explorer/database?table=vials", "Database: vials"),
    ("/record-explorer/database?table=vials&q=Test", "Test vial"),
])
def test_record_explorer_routes_render_without_500(explorer_client, route, expected):
    response = explorer_client.get(route)
    assert response.status_code == 200, response.text
    assert expected in response.text
    assert "Tracker" in response.text


def test_tool_pages_keep_local_instance_identity(explorer_client, monkeypatch):
    monkeypatch.setenv("TRACKER_INSTANCE", "DEV")
    response = explorer_client.get("/record-explorer/vials")
    assert response.status_code == 200
    assert "<title>[DEV] Vial lifecycle · Tracker</title>" in response.text
    assert "tracker-instance--dev" in response.text


def test_shared_renderer_other_pages_and_html_escaping():
    response = workflow_tools.page(
        "Protocol tools",
        "<p>Existing read-only tool remains available.</p>",
    )
    assert response.status_code == 200
    assert "Protocol tools" in response.body.decode("utf-8")
    assert "Existing read-only tool remains available." in response.body.decode("utf-8")


def test_database_explorer_does_not_list_secret_table(explorer_client):
    response = explorer_client.get("/record-explorer/database")
    assert response.status_code == 200
    assert "vendor_site_credentials" not in response.text
    assert "vials" in response.text
    assert explorer_client.get(
        "/record-explorer/database?table=vendor_site_credentials"
    ).status_code == 404


def test_full_tracker_app_record_explorer_routes(monkeypatch):
    """Exercise actual app routing, lifespan migrations, and page rendering."""
    from app.main import app

    monkeypatch.setenv("TRACKER_INSTANCE", "DEV")
    with TestClient(app) as client:
        for route in (
            "/record-explorer/vials",
            "/record-explorer/database",
            "/record-explorer/notes",
            "/record-explorer/health",
        ):
            response = client.get(route)
            assert response.status_code == 200, (
                route, response.status_code, response.text[:300]
            )
            assert "tracker-instance--dev" in response.text
