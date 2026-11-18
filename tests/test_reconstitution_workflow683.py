"""Release 683: vial picker provenance and single-field reconstitution workflow."""
from datetime import date
from html.parser import HTMLParser
import re

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Coa, Compound, PreparationEvent, Purchase, Vial


class _NumberInputs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = []

    def handle_starttag(self, tag, attrs):
        if tag == "input":
            self.inputs.append(dict(attrs))


def _inputs(html):
    parser = _NumberInputs()
    parser.feed(html)
    return parser.inputs


def test_683_picker_displays_vendor_lot_and_untracked_fallback():
    with TestClient(app) as client:
        with SessionLocal() as db:
            compound = Compound(name="Recon683 Vendor Lookup", primary_unit="mg")
            purchase = Purchase(vendor="Recon683 Supplier", purchased_on=date(2026, 11, 18))
            db.add_all([compound, purchase])
            db.flush()
            vial = Vial(compound_id=compound.id, purchase_id=purchase.id,
                        content_value=11, content_unit="mg", status="sealed",
                        lot="RECON683-LOT")
            db.add(vial)
            db.commit()
            vid = vial.id
        page = client.get("/reconstitution-calculator").text
        option = re.search(r'<option value="' + str(vid) + r'"[^>]*>(.*?)</option>', page, re.S)
        assert option, "new vial missing from picker"
        assert "Recon683 Supplier" in option.group(1)
        assert "RECON683-LOT" in option.group(1)
        assert "Vendor:" in option.group(1)
        assert "Lot:" in option.group(1)


def test_683_vial_reconstitution_uses_one_submittable_water_field_and_coa_mean():
    with TestClient(app) as client:
        with SessionLocal() as db:
            compound = Compound(name="Recon683 COA Arithmetic", primary_unit="IU")
            db.add(compound)
            db.flush()
            vial = Vial(compound_id=compound.id, content_value=24,
                        content_unit="IU", form="lyophilized", status="sealed",
                        use_coa_content=True)
            db.add(vial)
            db.flush()
            vial.coa = Coa(reported_content_value=29.47,
                           reported_content_unit="IU")
            db.commit()
            vid = vial.id

        page = client.get(f"/vials/{vid}")
        assert page.status_code == 200
        html = page.text
        fields = _inputs(html)
        content = next(f for f in fields if f.get("id") == "rc-content")
        water = [f for f in fields if f.get("name") == "volume_ml"
                 and f.get("form") == "recon-record-form683"]
        assert len(water) == 1, water
        assert float(content["value"]) == pytest.approx(29.47)
        assert 'Vial content (IU)' in html
        assert 'id="recon-record-form683"' in html
        assert 'id="vial-reconstitution683" open' in html
        assert "Record reconstitution: liquid added (mL)" not in html
        with SessionLocal() as db:
            saved = db.get(Vial, vid)
            assert saved.volume_ml is None
            assert saved.content_value == 24

        response = client.post(f"/vials/{vid}/reconstitute",
                               data={"volume_ml": "2.31"}, follow_redirects=False)
        assert response.status_code == 303
        with SessionLocal() as db:
            saved = db.get(Vial, vid)
            assert saved.volume_ml == pytest.approx(2.31)
            assert saved.status == "in_use"
            assert saved.content_value == pytest.approx(24)
            events = db.query(PreparationEvent).filter_by(
                vial_id=vid, kind="reconstitution").all()
            assert len(events) == 1

        saved_page = client.get(f"/vials/{vid}").text
        assert 'value="2.31"' in saved_page
        assert 'id="recon-record-form683"' not in saved_page


def test_683_without_coa_still_uses_label_and_no_record_form_for_liquid():
    with TestClient(app) as client:
        with SessionLocal() as db:
            compound = Compound(name="Recon683 Label Control", primary_unit="mg")
            db.add(compound)
            db.flush()
            vial = Vial(compound_id=compound.id, content_value=10,
                        content_unit="mg", status="in_use", form="solution",
                        volume_ml=3.0)
            db.add(vial)
            db.commit()
            vid = vial.id
        page = client.get(f"/vials/{vid}").text
        fields = _inputs(page)
        content = next(f for f in fields if f.get("id") == "rc-content")
        assert float(content["value"]) == pytest.approx(10)
        assert 'id="recon-record-form683"' not in page
        assert not [f for f in fields if f.get("name") == "volume_ml"
                    and f.get("form") == "recon-record-form683"]


def test_683_browser_formdata_uses_calculator_field():
    from playwright.sync_api import sync_playwright
    import os

    with TestClient(app) as client:
        with SessionLocal() as db:
            compound = Compound(name="Recon683 Browser Form", primary_unit="mg")
            db.add(compound)
            db.flush()
            vial = Vial(compound_id=compound.id, content_value=6,
                        content_unit="mg", status="sealed", form="lyophilized")
            db.add(vial)
            db.commit()
            vid = vial.id
        html = client.get(f"/vials/{vid}").text
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page()
            page.set_content(html)
            field = page.locator("#rc-water")
            field.fill("2.45")
            actual = page.locator("#recon-record-form683").evaluate(
                "form => [...new FormData(form).getAll('volume_ml')]"
            )
            assert actual == ["2.45"]
            assert page.locator('input[name="volume_ml"][form="recon-record-form683"]').count() == 1
        finally:
            browser.close()
