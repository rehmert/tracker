"""Release 627: signed, read-only blend planners with real synthetic stock.

The isolated Chromium runner supplies a disposable database. This module
creates and deletes its own sealed vials and never records a real blend.
Tests prove previews work with valid inputs and leave inventory unchanged.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from playwright.sync_api import sync_playwright

BASE_HTTP = os.environ.get("TRACKER_TEST_URL", "").rstrip("/")
BASE_HTTPS = os.environ.get("TRACKER_TEST_HTTPS_URL", "").rstrip("/")
DATA = Path(os.environ.get("TRACKER_BROWSER_QA_DATA_DIR", "/")).resolve()
HTTP, HTTPS = urlsplit(BASE_HTTP), urlsplit(BASE_HTTPS)

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
    raise RuntimeError("627 blend planner QA requires disposable strict environment")

# Bind app.config imports in this pytest worker to the same verified\n# disposable data directory as the isolated Uvicorn process.\nos.environ["TRACKER_DATA_DIR"] = str(DATA)\n\npytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        chromium = playwright.chromium.launch(headless=True)
        yield chromium
        chromium.close()


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_627_signed_blend_preview_routes_are_read_only(browser, scheme):
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from app.models import Blend, Compound, Vial

    # Pytest's process is separate from the isolated Uvicorn process.
    # Do not use app.db.SessionLocal: its engine is bound at import time
    # and may silently target a different SQLite database.
    database = DATA / "tracker.db"
    assert database.parent == DATA and database.is_file()
    assert not database.is_symlink() and not DATA.is_symlink()
    qa_engine = create_engine(
        "sqlite:///" + str(database),
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(qa_engine, "connect")
    def _set_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    SessionLocal = sessionmaker(bind=qa_engine, expire_on_commit=False)

    base = BASE_HTTP if scheme == "http" else BASE_HTTPS
    name = "QA627 blend preview " + uuid4().hex[:12]
    ids = []
    compound_ids = []

    # Fixture creation is strictly local to tracker-browser-qa.* /data.
    # Test never imports the installed Tracker instance or real data.
    with SessionLocal() as db:
        for index in range(3):
            compound = Compound(
                name=name + " compound " + str(index),
                category="peptide", primary_unit="mg",
            )
            db.add(compound)
            db.flush()
            compound_ids.append(compound.id)
            if index < 2:
                liquid = Vial(
                    compound_id=compound.id, label=name + " liquid " + str(index),
                    content_value=10 * (index + 1),
                    content_unit="mg", volume_ml=1, status="sealed",
                )
                dry = Vial(
                    compound_id=compound.id, label=name + " dry " + str(index),
                    content_value=10 * (index + 1),
                    content_unit="mg", status="sealed",
                )
                db.add_all([liquid, dry])
                db.flush()
                ids.extend([liquid.id, dry.id])
            else:
                for ordinal in range(3):
                    dry = Vial(
                        compound_id=compound.id,
                        label=name + " waterfall " + str(ordinal),
                        content_value=5, content_unit="mg", status="sealed",
                    )
                    db.add(dry)
                    db.flush()
                    ids.append(dry.id)
        db.commit()
        baseline_blends = db.query(Blend).count()

    context = browser.new_context(ignore_https_errors=True)
    try:
        page = context.new_page()
        landing = page.goto(base + "/blends", wait_until="networkidle")
        assert landing is not None and landing.status == 200
        token = page.evaluate("window.trackerCsrfToken?.() || ''")
        assert token.startswith("v1.")

        def preview(path, pairs, heading):
            denied = page.request.post(
                base + path, form={"label": name}, max_redirects=0,
            )
            assert denied.status == 403, (scheme, path, "unsigned", denied.status)
            result = page.evaluate(
                """async ({path,pairs,token}) => {
                    const body = new FormData();
                    for (const [key,value] of pairs) body.append(key,value);
                    const response = await fetch(path,{
                        method:'POST',credentials:'same-origin',
                        headers:{'X-Tracker-CSRF':token},body,
                    });
                    return {status:response.status,body:await response.text(),
                            report:response.headers.get('x-tracker-csrf-report')};
                }""",
                {"path": path, "pairs": pairs, "token": token},
            )
            assert result["status"] == 200, (
                scheme, path, result["status"], result["body"][:300],
            )
            assert result["report"] == "valid", (scheme, path)
            assert heading in result["body"], (scheme, path, result["body"][:400])

        # Two liquid source vials, balanced target shares.
        liquid = [
            ("label", name + " normal"), ("diluent_ml", "0"),
            ("capacity_ml", "3"),
            ("source_id", str(ids[0])), ("source_id", str(ids[2])),
            ("transfer_amount", "10"), ("transfer_amount", "20"),
            ("transfer_unit", "mg"), ("transfer_unit", "mg"),
            ("target_amount", "1"), ("target_amount", "2"),
            ("target_unit", "mg"), ("target_unit", "mg"),
        ]
        preview("/blends/preview", liquid, "Preview only.")

        recon = [
            ("source_id", str(ids[1])), ("source_id", str(ids[3])),
            ("target_amount", "1"), ("target_amount", "2"),
            ("target_unit", "mg"), ("target_unit", "mg"),
            ("source_bac_ml", "0.5"), ("source_bac_ml", "0.5"),
            ("planner_draw_ml", "0.2"), ("planner_capacity_ml", "3"),
            ("planner_allocation", "equal"),
        ]
        preview("/blends/reconstitution-preview", recon,
                "No inventory has been changed.")

        water = [
            ("label", name + " waterfall"),
            ("waterfall_source_id", str(ids[4])),
            ("waterfall_source_id", str(ids[5])),
            ("waterfall_source_id", str(ids[6])),
            ("waterfall_bac_ml", "0.5"),
            ("waterfall_capacity_ml", "3"),
            ("waterfall_target_amount", "1"),
            ("waterfall_target_unit", "mg"),
        ]
        preview("/blends/waterfall/preview", water, "not recorded")

        with SessionLocal() as db:
            assert db.query(Blend).count() == baseline_blends
            for vid in ids:
                vial = db.get(Vial, vid)
                assert vial is not None and vial.status == "sealed"
            assert all(db.get(Vial, vid).volume_ml is None
                       for vid in (ids[1], ids[3], ids[4], ids[5], ids[6]))
    finally:
        context.close()
        # All created records belong to this one ephemeral test. Do not
        # inadvertently delete other browser-module fixture vials.
        with SessionLocal() as db:
            for vid in ids:
                item = db.get(Vial, vid)
                if item is not None:
                    db.delete(item)
            db.flush()
            for cid in compound_ids:
                compound = db.get(Compound, cid)
                if compound is not None:
                    db.delete(compound)
            db.commit()
        qa_engine.dispose()
