"""Release 586: read-only Chromium field geometry on disposable candidate pages.

All checks stay on a localhost QA instance. The synthetic edit record is
created only in the disposable QA database. No live account or stock access.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from playwright.sync_api import sync_playwright

URL = os.environ.get("TRACKER_TEST_URL", "").rstrip("/")
DATA = Path(os.environ.get("TRACKER_BROWSER_QA_DATA_DIR", "/")).resolve()

if not (
    os.environ.get("TRACKER_TEST_ISOLATED") == "1"
    and re.fullmatch(r"http://127[.]0[.]0[.]1:[0-9]+", URL)
    and DATA.name == "data" and DATA.parent.parent == Path("/tmp")
    and re.fullmatch(r"tracker-browser-qa[.][A-Za-z0-9_]{8}", DATA.parent.name)
):
    raise RuntimeError("Release 586 geometry tests require disposable localhost QA")

pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        chromium = p.chromium.launch(headless=True)
        yield chromium
        chromium.close()


@pytest.fixture(scope="module")
def synthetic_edit_id():
    from app.db import SessionLocal
    from app.models import Compound, DoseLog, Vial

    with SessionLocal() as db:
        compound = Compound(name="QA geometry 586 " + uuid4().hex, category="peptide")
        db.add(compound)
        db.flush()
        vial = Vial(compound_id=compound.id, content_value=20, content_unit="mg",
                    volume_ml=2, status="in_use")
        db.add(vial)
        db.flush()
        dose = DoseLog(vial_id=vial.id, taken_at=datetime(2026, 11, 12, 13, 30),
                       entered_value=1, entered_unit="mg", amount_base=1000,
                       kind="dose", site="", notes="")
        db.add(dose)
        db.commit()
        return dose.id


# Existing navigation targets, rather than guessed backend endpoints.
PAGES = (
    "/doses", "/vials", "/purchases", "/supplies",
    "/compounds", "/vitals", "/labs", "/protocols",
    "/dose-workspace", "/calendar",
)


def collisions(page):
    return page.evaluate("""() => {
      const failures = [];
      const epsilon = 2;
      const visible = (node) => {
        const style = getComputedStyle(node);
        const r = node.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden'
          && r.width > 0 && r.height > 0;
      };
      for (const label of document.querySelectorAll(
        '#main-content form .grid > label.field, ' +
        '#main-content form.grid > label.field'
      )) {
        if (!visible(label)) continue;
        const outer = label.getBoundingClientRect();
        for (const input of label.querySelectorAll(
          'input:not([type=hidden]):not([type=checkbox]), select, textarea'
        )) {
          if (!visible(input)) continue;
          const rect = input.getBoundingClientRect();
          if (rect.left < outer.left - epsilon ||
              rect.right > outer.right + epsilon) {
            failures.push('Field extends outside label: ' +
              (input.name || input.type || 'unnamed'));
          }
        }
      }
      const enhanced = document.querySelectorAll('.tracker-time24-controls');
      for (const group of enhanced) {
        if (!visible(group)) continue;
        const controls = [...group.querySelectorAll('input,button')]
          .filter(visible).map(el => [el, el.getBoundingClientRect()]);
        for (let i = 0; i < controls.length; i++) {
          for (let j = i + 1; j < controls.length; j++) {
            const a = controls[i][1], b = controls[j][1];
            if (a.left < b.right - epsilon &&
                b.left < a.right - epsilon &&
                a.top < b.bottom - epsilon &&
                b.top < a.bottom - epsilon) {
              failures.push('Overlapping date/time controls: ' +
                controls[i][0].className + ' and ' +
                controls[j][0].className);
            }
          }
        }
      }
      return failures;
    }""")


@pytest.mark.parametrize("width", (1440, 800, 390))
def test_586_key_form_pages_have_no_field_overlaps(browser, width):
    context = browser.new_context(viewport={"width": width, "height": 900})
    page = context.new_page()
    try:
        for route in PAGES:
            response = page.goto(URL + route, wait_until="networkidle", timeout=30000)
            assert response is not None and response.status == 200, (route, response.status if response else None)
            assert not collisions(page), (width, route, collisions(page))
    finally:
        context.close()


@pytest.mark.parametrize("width", (1440, 800, 390, 320))
def test_586_dose_edit_datetime_and_fields_do_not_overlap(browser, synthetic_edit_id, width):
    context = browser.new_context(viewport={"width": width, "height": 900})
    page = context.new_page()
    try:
        response = page.goto(URL + f"/doses/{synthetic_edit_id}/edit",
                             wait_until="networkidle", timeout=30000)
        assert response is not None and response.status == 200
        group = page.locator("#tracker-dose-correction-form .tracker-time24-controls")
        assert group.count() == 1
        assert group.locator(".tracker-time24-date").count() == 1
        assert group.locator(".tracker-time24-clock").count() == 1
        assert group.locator(".tracker-time24-now").count() == 1
        assert not collisions(page), (width, collisions(page))
        field = page.locator("#tracker-dose-correction-form .tracker-dose-when-field")
        bounding = field.bounding_box()
        assert bounding and bounding["width"] > 200
    finally:
        context.close()


def test_586_dose_history_shows_vial_identity(browser, synthetic_edit_id):
    from app.db import SessionLocal
    from app.models import DoseLog, Vial
    with SessionLocal() as db:
        vial_id = db.get(DoseLog, synthetic_edit_id).vial_id
        compound_id = db.get(Vial, vial_id).compound_id
    context = browser.new_context()
    page = context.new_page()
    try:
        response = page.goto(URL + f"/doses?compound_id={compound_id}",
                             wait_until="networkidle")
        assert response is not None and response.status == 200
        assert page.locator("#dose-history thead th").all_text_contents().count("Vial") == 1
        assert page.locator(
            f'#dose-body a[href="/vials/{vial_id}"]'
        ).count() >= 1
    finally:
        context.close()
