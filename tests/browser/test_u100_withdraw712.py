"""Release 712: one U-100 syringe-unit withdrawal via real browser over HTTP/HTTPS.

Requires isolated localhost Chromium with strict CSRF and a disposable
test database. Never touches installed DEV or production inventory.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from playwright.sync_api import expect, sync_playwright

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
    and DATA.is_dir() and DATA.name == "data" and not DATA.is_symlink()
    and DATA.parent.parent == Path("/tmp").resolve()
    and re.fullmatch(r"tracker-browser-qa[.][A-Za-z0-9_]{8}", DATA.parent.name)
):
    raise RuntimeError("712 browser test refuses non-disposable strict QA")

pytestmark = pytest.mark.browser
DB = DATA / "tracker.db"


def row(sql, args=()):
    assert DB.is_file() and DB.resolve().parent == DATA
    with sqlite3.connect(DB, timeout=20) as db:
        return db.execute(sql, args).fetchone()


def seed(scheme):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.models import Blend, BlendComponent, Compound, Vial

    eng = create_engine("sqlite:///" + str(DB),
                        connect_args={"check_same_thread": False})
    name = "QA712-" + scheme + "-" + uuid4().hex[:12]
    with Session(eng) as db:
        compound = Compound(name=name + "-single")
        db.add(compound)
        db.flush()
        ordinary = Vial(
            compound_id=compound.id, content_value=10,
            content_unit="mg", volume_ml=2, status="in_use",
        )
        db.add(ordinary)
        db.flush()
        source_vials, compounds = [], []
        for i in range(2):
            c = Compound(name=name + "-blend-" + str(i))
            db.add(c)
            db.flush()
            v = Vial(compound_id=c.id, content_value=10 * (i + 1),
                     content_unit="mg", volume_ml=1, status="finished")
            db.add(v)
            db.flush()
            source_vials.append(v)
            compounds.append(c)
        blend = Blend(label=name + "-prepared", final_volume_ml=2,
                      diluent_ml=0, status="in_use")
        db.add(blend)
        db.flush()
        for i in range(2):
            db.add(BlendComponent(
                blend_id=blend.id, source_vial_id=source_vials[i].id,
                compound_id=compounds[i].id, transferred_base=10000 * (i + 1),
                transferred_ml=1, target_dose_base=1000 * (i + 1),
                target_unit="mg",
            ))
        db.commit()
        result = ordinary.id, blend.id, [v.id for v in source_vials]
    eng.dispose()
    return result


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_712_u100_syringe_units_in_real_shared_browser_form(scheme):
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    vid, bid, source_ids = seed(scheme)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        try:
            page = context.new_page()
            landing = page.goto(base + "/doses", wait_until="networkidle")
            assert landing is not None and landing.status == 200
            form = page.locator('form[hx-post="/doses"]')
            assert form.count() == 1
            picker = form.locator('select[name="vial_id"]')
            unit = form.locator('select[name="unit"]')
            expect(unit.locator('option[value="units"]')).to_have_text(
                "units (U-100 syringe)"
            )
            expect(unit.locator('option[value="IU"]')).to_have_text("IU")
            picker.select_option(str(vid))
            unit.select_option("units")
            form.locator('input[name="amount"]').fill("20")
            expect(page.locator("#dose-preview")).to_contain_text("0.2 mL")
            token = page.evaluate("window.trackerCsrfToken?.() || ''")
            assert token.startswith("v1.")
            saved_vial = page.request.post(
                base + "/doses",
                form={
                    "vial_id": str(vid), "amount": "20", "unit": "units",
                    "taken_at": "2026-11-20T10:10", "kind": "dose",
                    "site": "Abdomen lower right",
                    "submission_token": str(uuid4()),
                },
                headers={"X-Tracker-CSRF": token}, max_redirects=0,
            )
            assert saved_vial.status == 200
            value = row(
                "SELECT entered_value,entered_unit,amount_base FROM dose_logs WHERE vial_id=?",
                (vid,),
            )
            assert value == (20.0, "units", 1000.0)

            # Switching a physical source clears an unsafe old amount, but
            # keeps the U-100 volume unit rather than silently changing it.
            picker.select_option(f"blend:{bid}")
            expect(form.locator('input[name="amount"]')).to_have_value("")
            expect(unit).to_have_value("units")
            form.locator('input[name="amount"]').fill("20")
            expect(page.locator("#dose-preview")).to_contain_text("0.2 mL")
            expect(page.locator("#dose-preview")).to_contain_text("2 mg")
            saved_blend = page.request.post(
                base + "/doses",
                form={
                    "vial_id": f"blend:{bid}", "amount": "20", "unit": "units",
                    "taken_at": "2026-11-20T10:20", "kind": "dose",
                    "site": "Abdomen lower right",
                    "submission_token": str(uuid4()),
                },
                headers={"X-Tracker-CSRF": token, "HX-Request": "true"},
                max_redirects=0,
            )
            assert saved_blend.status == 200, saved_blend.text()
            result = row(
                "SELECT volume_ml, entered_value, entered_unit FROM blend_doses WHERE blend_id=?",
                (bid,),
            )
            assert result == (.2, 20.0, "units")
            assert row("SELECT COUNT(*) FROM dose_logs WHERE vial_id IN (?, ?)",
                       tuple(source_ids)) == (0,)
            print("TARGETED_712_U100_WITHDRAW=PASSED_" + scheme, flush=True)
        finally:
            context.close()
            browser.close()
