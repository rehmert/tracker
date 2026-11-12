"""587–588: signed browser fetch bulk-vial lifecycle, isolated HTTP and HTTPS.

Uses an explicitly guarded disposable browser-server SQLite database, not the
independent pytest-worker database. Exercises actual browser's global fetch
CSRF wrapper; no installed data and no production mutations.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from playwright.sync_api import sync_playwright

HTTP_URL = os.environ.get("TRACKER_TEST_URL", "").rstrip("/")
HTTPS_URL = os.environ.get("TRACKER_TEST_HTTPS_URL", "").rstrip("/")
DATA = Path(os.environ.get("TRACKER_BROWSER_QA_DATA_DIR", "/")).resolve()
HTTP, HTTPS = urlsplit(HTTP_URL), urlsplit(HTTPS_URL)
if not (
    os.environ.get("TRACKER_TEST_ISOLATED") == "1"
    and os.environ.get("TRACKER_TEST_STRICT_CSRF") == "1"
    and HTTP.scheme == "http" and HTTPS.scheme == "https"
    and HTTP.hostname == HTTPS.hostname == "127.0.0.1"
    and HTTP.port not in (None, 8000)
    and HTTPS.port not in (None, 443, 8000, HTTP.port)
    and DATA.name == "data" and DATA.is_dir()
    and DATA.parent.parent == Path("/tmp").resolve()
    and re.fullmatch(r"tracker-browser-qa[.][A-Za-z0-9_]{8}", DATA.parent.name)
):
    raise RuntimeError("587/588 bulk QA must run in disposable strict localhost")

pytestmark = pytest.mark.browser
ROUTES = (
    ("/vials/bulk/validate-selection", 200),
    ("/vials/bulk/preview", 200),
    ("/vials/bulk", 303),
    ("/vials/bulk/delete-preview", 200),
    ("/vials/bulk/delete", 303),
)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture
def tab(browser):
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    yield page, errors
    context.close()


@pytest.fixture
def synthetic_vial():
    # tests/conftest.py intentionally overrides TRACKER_DATA_DIR. Use an
    # explicitly verified independent browser server DB, never app.db.engine.
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import Session
    from app.models import Compound, Vial

    path = (DATA / "tracker.db").resolve()
    assert path.parent == DATA and path.is_file() and not path.is_symlink()
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def _pragmas(conn, _record):
        conn.execute("PRAGMA foreign_keys=ON")
    try:
        with Session(engine) as db:
            compound = Compound(name="QA strict bulk " + uuid4().hex, primary_unit="mg")
            db.add(compound)
            db.flush()
            vial = Vial(compound_id=compound.id, content_value=10,
                        content_unit="mg", status="sealed", label="QA bulk 587")
            db.add(vial)
            db.flush()
            vial_id = vial.id
            db.commit()
        yield vial_id
        # The test intentionally deletes its vial; if an assertion stops
        # early, no cleanup write is performed outside disposable QA data.
    finally:
        engine.dispose()


def _browser_write(page, path, fields):
    """Use the page's actual patched fetch() and a native FormData body."""
    with page.expect_response(lambda response: (
        response.request.method == "POST"
        and urlsplit(response.url).path == path
    )) as pending:
        result = page.evaluate("""async ({path, fields}) => {
      const data = new FormData();
      for (const [key, value] of fields) data.append(key, String(value));
      const response = await fetch(path, {
        method: 'POST', body: data, credentials: 'same-origin',
        redirect: 'follow'
      });
      return {
        status: response.status,
        csrf: response.headers.get('x-tracker-csrf-report'),
        body: await response.text(),
        destination: response.url,
      };
    }""", {"path": path, "fields": fields})
    signed = pending.value
    assert signed.headers.get("x-tracker-csrf-report") == "valid", (path, signed.status)
    assert signed.request.all_headers().get("x-tracker-csrf", "").startswith("v1.")
    assert signed.status in (200, 303), (path, signed.status)
    return result


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_587_588_bulk_vial_preview_update_delete_strict(tab, synthetic_vial, scheme):
    page, errors = tab
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    response = page.goto(base + "/vials", wait_until="networkidle")
    assert response is not None and response.status == 200
    token = page.evaluate("window.trackerCsrfToken?.() || ''")
    assert token.startswith("v1.")
    vial_id = synthetic_vial
    ids = [["vial_ids", str(vial_id)]]
    for path, _ in ROUTES:
        rejected = page.request.post(base + path, data=dict(ids), max_redirects=0)
        assert rejected.status == 403, (scheme, path, rejected.status)
        assert "CSRF token required" in rejected.text()

    verified = _browser_write(page, ROUTES[0][0], ids)
    assert verified["status"] == 200 and json.loads(verified["body"])["found"] == 1

    changes = ids + [["mode_label", "set"], ["value_label", "QA bulk edited " + scheme]]
    preview = _browser_write(page, ROUTES[1][0], changes)
    assert preview["status"] == 200
    preview_json = json.loads(preview["body"])
    assert preview_json["ok"] is True and preview_json["count"] == 1
    assert preview_json["snapshot"]
    updated = _browser_write(
        page, ROUTES[2][0],
        changes + [["bulk_preview_snapshot", preview_json["snapshot"]]]
    )
    assert updated["status"] == 200 and "msg=" in updated["destination"], updated
    assert "err=" not in updated["destination"]

    detail = page.request.get(base + "/vials/" + str(vial_id))
    assert detail.status == 200
    assert "QA bulk edited " + scheme in detail.text()

    removal = _browser_write(page, ROUTES[3][0], ids)
    assert removal["status"] == 200
    deletion = json.loads(removal["body"])
    assert deletion["ok"] and len(deletion["eligible"]) == 1
    assert deletion["snapshot"]
    removed = _browser_write(
        page, ROUTES[4][0],
        ids + [["delete_preview_snapshot", deletion["snapshot"]]]
    )
    assert removed["status"] == 200 and "msg=" in removed["destination"], removed
    assert "err=" not in removed["destination"]
    assert page.request.get(base + "/vials/" + str(vial_id)).status == 404
    # Independently reconcile the disposable server database after the
    # HTTP lifecycle. A 303 alone is not evidence that writes persisted.
    db_file = (DATA / "tracker.db").resolve()
    assert db_file.parent == DATA and db_file.is_file() and not db_file.is_symlink()
    with sqlite3.connect(db_file) as db:
        assert db.execute("SELECT COUNT(*) FROM vials WHERE id=?", (vial_id,)).fetchone()[0] == 0
        actions = [row[0] for row in db.execute(
            "SELECT action FROM change_audit WHERE entity_type='vial' "
            "AND entity_id=? ORDER BY id", (vial_id,)
        )]
        assert actions == ["bulk_update", "bulk_delete"], actions
    assert not errors, errors

    folder = DATA.parent / "csrf-runtime587"
    folder.mkdir(mode=0o700, exist_ok=True)
    receipt = folder / (scheme + "-bulk.json")
    payload = {
        "scheme": scheme,
        "flow": "vial-bulk-fetch-lifecycle",
        "operations": [
            {"method": "POST", "route_pattern": path,
             "signed_status": status, "unsigned_status": 403}
            for path, status in ROUTES
        ],
        "synthetic_qa_data_only": True,
        "signed_browser_fetch": True,
        "redirects_followed_and_success_flash_verified": True,
        "native_bulk_form_submission_tested": False,
        "csrf_enforcement_installed": False,
        "persisted_update_and_delete_verified": True,
    }
    with receipt.open("x", encoding="utf-8") as output:
        json.dump(payload, output, sort_keys=True)
        output.write("\n")
    receipt.chmod(0o600)
