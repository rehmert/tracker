"""Release 711: real HTTP/HTTPS strict-CSRF blend correction and deletion.

Only a disposable localhost QA database may be used. Mutations go through
the rendered correction form and its native signed submit lifecycle.
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
    raise RuntimeError("711 browser test refuses non-disposable strict QA")

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

    eng = create_engine("sqlite:///" + str(DB), connect_args={"check_same_thread": False})
    label = "QA711-" + scheme + "-" + uuid4().hex[:12]
    with Session(eng) as db:
        compounds, vials = [], []
        for i in range(2):
            compound = Compound(name=f"{label}-compound-{i}")
            db.add(compound)
            db.flush()
            vial = Vial(compound_id=compound.id, content_value=10 * (i + 1),
                        content_unit="mg", volume_ml=1, status="finished")
            db.add(vial)
            db.flush()
            compounds.append(compound)
            vials.append(vial)
        blend = Blend(label=label, final_volume_ml=2, status="in_use")
        db.add(blend)
        db.flush()
        for i, (compound, vial) in enumerate(zip(compounds, vials)):
            db.add(BlendComponent(
                blend_id=blend.id, compound_id=compound.id,
                source_vial_id=vial.id, transferred_base=10000 * (i + 1),
                transferred_ml=1, target_dose_base=1000 * (i + 1),
                target_unit="mg",
            ))
        db.commit()
        values = blend.id, [v.id for v in vials]
    eng.dispose()
    return values


@pytest.mark.parametrize("scheme", ("http", "https"))
def test_711_signed_browser_edit_delete_restore_blend_volume_and_audit(scheme):
    base = HTTP_URL if scheme == "http" else HTTPS_URL
    bid, source_ids = seed(scheme)
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        try:
            page = context.new_page()
            landing = page.goto(base + "/doses?source=blend:" + str(bid),
                                wait_until="networkidle")
            assert landing and landing.status == 200
            token = page.evaluate("window.trackerCsrfToken?.() || ''")
            assert token.startswith("v1.")
            create = page.request.post(
                base + "/doses",
                form={
                    "vial_id": f"blend:{bid}",
                    "amount": ".2", "unit": "mL",
                    "taken_at": "2026-11-19T07:30", "kind": "dose",
                    "site": "Quadriceps left",
                    "submission_token": str(uuid4()),
                },
                headers={"X-Tracker-CSRF": token, "HX-Request": "true"},
                max_redirects=0,
            )
            assert create.status == 200, create.text()
            did = row("SELECT id FROM blend_doses WHERE blend_id=?", (bid,))[0]
            assert row("SELECT volume_ml FROM blend_doses WHERE id=?", (did,)) == (.2,)
            timeline = page.goto(base + "/doses", wait_until="networkidle")
            assert timeline and timeline.status == 200
            link = page.locator(
                f'a[href="/doses/blends/{did}/edit"]'
            ).first
            expect(link).to_be_visible()
            link.click()
            expect(page.locator("#tracker-dose-correction-form")).to_be_visible()
            assert page.locator('select[name="unit"] option[value="mg"]').count() == 0

            edit_url = f"/doses/blends/{did}/edit"
            rejected = page.request.post(base + edit_url, form={
                "taken_at": "2026-11-19T08:00", "amount": ".5",
                "unit": "mL", "kind": "waste",
            }, max_redirects=0)
            assert rejected.status == 403
            forged = page.request.post(base + edit_url, form={
                "taken_at": "2026-11-19T08:00", "amount": ".5",
                "unit": "mL", "kind": "waste",
            }, headers={"X-Tracker-CSRF": "forged-711"}, max_redirects=0)
            assert forged.status == 403
            assert row("SELECT volume_ml FROM blend_doses WHERE id=?", (did,)) == (.2,)

            form = page.locator("#tracker-dose-correction-form")
            form.locator('input[name="amount"]').fill("0.45")
            form.locator('select[name="kind"]').select_option("waste")
            with page.expect_response(
                lambda result: urlsplit(result.url).path == edit_url
                and result.request.method == "POST"
            ) as pending:
                form.get_by_role("button", name="Save correction").click()
            saved = pending.value
            assert saved.status == 303
            assert saved.headers.get("x-tracker-csrf-report") == "valid"
            assert row("SELECT volume_ml,kind FROM blend_doses WHERE id=?",
                       (did,)) == (.45, "waste")
            assert row("SELECT COUNT(*) FROM change_audit WHERE "
                       "entity_type='blend_dose' AND entity_id=?", (did,)) == (1,)
            assert row("SELECT COUNT(*) FROM dose_logs WHERE vial_id IN (?,?)",
                       tuple(source_ids)) == (0,)

            detail = page.goto(base + edit_url, wait_until="networkidle")
            assert detail and detail.status == 200
            assert "Change history" in page.content()
            delete_url = f"/doses/blends/{did}/delete"
            unsafe = page.request.post(
                base + delete_url, form={"confirm_delete": "yes"},
                max_redirects=0,
            )
            assert unsafe.status == 403
            assert row("SELECT COUNT(*) FROM blend_doses WHERE id=?", (did,)) == (1,)
            delete_form = page.locator(f'form[action="{delete_url}"]')
            delete_form.locator('input[name="confirm_delete"]').check()
            with page.expect_response(
                lambda result: urlsplit(result.url).path == delete_url
                and result.request.method == "POST"
            ) as pending_delete:
                delete_form.get_by_role("button", name="Delete withdrawal").click()
            deleted = pending_delete.value
            assert deleted.status == 303
            assert deleted.headers.get("x-tracker-csrf-report") == "valid"
            assert row("SELECT COUNT(*) FROM blend_doses WHERE id=?", (did,)) == (0,)
            assert row("SELECT status FROM blends WHERE id=?", (bid,)) == ("in_use",)
            assert row("SELECT COUNT(*) FROM change_audit WHERE "
                       "entity_type='blend_dose' AND entity_id=?", (did,)) == (2,)
            assert row("SELECT COUNT(*) FROM dose_logs WHERE vial_id IN (?,?)",
                       tuple(source_ids)) == (0,)
            print("BLEND_711_STRICT_CORRECTION_DELETE=PASSED_" + scheme, flush=True)
        finally:
            context.close()
            browser.close()
