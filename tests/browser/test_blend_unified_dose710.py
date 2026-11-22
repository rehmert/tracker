"""Release 710: real Chromium strict-CSRF unified physical-vial dose workflow.

HTTP and HTTPS each select a prepared mixed-compound vial from the normal
/doses form, calculate the actual draw, prove forged submissions cannot
alter stock, then persist exactly one BlendDose (never constituent DoseLogs).
"""
from __future__ import annotations
import os
from pathlib import Path
import re
import sqlite3
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
    and DATA.name == "data" and DATA.is_dir() and not DATA.is_symlink()
    and DATA.parent.parent == Path("/tmp").resolve()
    and re.fullmatch(r"tracker-browser-qa[.][A-Za-z0-9_]{8}", DATA.parent.name)
):
    raise RuntimeError("710 browser test refuses non-disposable strict QA")

pytestmark = pytest.mark.browser
DB = DATA / "tracker.db"


def read(sql, params=()):
    assert DB.is_file() and not DB.is_symlink() and DB.resolve().parent == DATA
    with sqlite3.connect(DB, timeout=20) as conn:
        return conn.execute(sql, params).fetchone()


def seed(scheme):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.models import Blend, BlendComponent, Compound, Vial
    qa = create_engine("sqlite:///" + str(DB), connect_args={"check_same_thread":False})
    name = "QA710-" + scheme + "-" + uuid4().hex[:12]
    with Session(qa) as db:
        compounds, vials = [], []
        for i in range(2):
            compound = Compound(name=name + "-compound-" + str(i))
            db.add(compound)
            db.flush()
            vial = Vial(compound_id=compound.id, content_value=10*(i+1),
                        content_unit="mg", volume_ml=1, status="finished")
            db.add(vial)
            db.flush()
            compounds.append(compound)
            vials.append(vial)
        blend = Blend(label=name, final_volume_ml=2,
                      diluent_ml=0, status="in_use")
        db.add(blend)
        db.flush()
        for i in range(2):
            db.add(BlendComponent(
                blend_id=blend.id, source_vial_id=vials[i].id,
                compound_id=compounds[i].id, transferred_base=10000*(i+1),
                transferred_ml=1, target_dose_base=1000*(i+1),
                target_unit="mg",
            ))
        db.commit()
        ids = blend.id, [v.id for v in vials], [c.name for c in compounds]
    qa.dispose()
    return ids


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_710_normal_vial_picker_accepts_real_blend_dose_and_rejects_forgery(scheme):
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    bid, sources, names = seed(scheme)
    with sync_playwright() as playwright:
        chromium = playwright.chromium.launch(headless=True)
        context = chromium.new_context(ignore_https_errors=True)
        try:
            page = context.new_page()
            landing = page.goto(
                base + f"/doses?source=blend:{bid}",
                wait_until="networkidle",
            )
            assert landing is not None and landing.status == 200
            form = page.locator('form[hx-post="/doses"]')
            assert form.count() == 1
            source = form.locator('select[name="vial_id"]')
            assert source.input_value() == f"blend:{bid}"
            assert page.locator("#dose-blend-select").count() == 0
            selected = source.locator("option:checked")
            assert selected.get_attribute("data-mixed") == "true"
            assert all(name in selected.inner_text() for name in names)
            assert form.locator('select[name="unit"]').input_value() == "mL"
            token = page.evaluate("window.trackerCsrfToken?.() || ''")
            assert isinstance(token, str) and token.startswith("v1.")
            cookie = next((c for c in context.cookies()
                           if c["name"] == "tracker_csrf_v1"), None)
            assert cookie is not None and cookie["value"] == token
            submission = form.locator('input[name="submission_token"]').input_value()
            assert re.fullmatch(r"[a-f0-9-]{36}", submission)

            preview = page.request.post(base + "/doses/preview", form={
                "vial_id": f"blend:{bid}", "amount": "0.2", "unit": "mL",
            }, headers={"X-Tracker-CSRF": token}, max_redirects=0)
            assert preview.status == 200
            assert all(name in preview.text() for name in names)
            assert "1 mg" in preview.text() and "2 mg" in preview.text()
            form_fields = {
                "vial_id": f"blend:{bid}", "amount": "0.2", "unit": "mL",
                "taken_at": "2026-11-18T10:45", "kind": "dose",
                "site": "Quadriceps left", "notes": "QA710 browser synthetic",
                "submission_token": submission,
            }
            baseline = read(
                "SELECT COUNT(*) FROM blend_doses WHERE blend_id=?", (bid,)
            )
            assert baseline == (0,)
            no_token = page.request.post(base + "/doses", form=form_fields,
                                         max_redirects=0)
            assert no_token.status == 403, no_token.status
            assert read("SELECT COUNT(*) FROM blend_doses WHERE blend_id=?",
                        (bid,)) == baseline
            forged = page.request.post(
                base + "/doses", form=form_fields,
                headers={"X-Tracker-CSRF": "forged-710-token"},
                max_redirects=0,
            )
            assert forged.status == 403, forged.status
            assert read("SELECT COUNT(*) FROM blend_doses WHERE blend_id=?",
                        (bid,)) == baseline
            saved = page.request.post(
                base + "/doses", form=form_fields,
                headers={"X-Tracker-CSRF": token, "HX-Request": "true"},
                max_redirects=0,
            )
            assert saved.status == 200, saved.status
            assert saved.headers.get("x-tracker-csrf-report") == "valid"
            assert saved.headers.get("hx-redirect") == (
                "/doses#dose-history-unified614"
            )
            recorded = read(
                "SELECT volume_ml,entered_value,entered_unit,site,kind "
                "FROM blend_doses WHERE blend_id=?", (bid,),
            )
            assert recorded == (0.2, 0.2, "mL", "Quadriceps left", "dose")
            assert read(
                "SELECT COUNT(*) FROM dose_logs WHERE vial_id IN (?,?)",
                tuple(sources),
            ) == (0,)
            assert read(
                "SELECT COUNT(*) FROM blend_doses WHERE blend_id=?", (bid,)
            ) == (1,)
            history = page.goto(base + "/doses", wait_until="networkidle")
            assert history is not None and history.status == 200
            row = page.locator(
                f'tr[data-timeline-source="blend"][data-physical-source="blend:{bid}"]'
            )
            assert row.count() == 1
            assert row.get_attribute("data-dose-site") == "Quadriceps left"
            print("BLEND_710_SIGNED_NORMAL_VIAL_FORM=PASSED_" + scheme, flush=True)
        finally:
            context.close()
            chromium.close()
