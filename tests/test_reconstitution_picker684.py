"""Release 684: verify user-visible vial picker provenance, not just option HTML."""
from datetime import date
import os

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from app.db import SessionLocal
from app.main import app
from app.models import Compound, Purchase, Vial


@pytest.mark.parametrize("width", [320, 390, 768, 1280])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_684_vial_picker_vendor_and_lot_visible_after_selection(width, scheme):
    with TestClient(app) as client:
        with SessionLocal() as db:
            compound = Compound(name="Recon684 Blue Peptide", primary_unit="mg")
            purchase = Purchase(vendor="Recon684 Example Supplier", purchased_on=date(2026, 11, 18))
            db.add_all([compound, purchase])
            db.flush()
            vial = Vial(compound_id=compound.id, purchase_id=purchase.id,
                        content_value=10, content_unit="mg", status="sealed",
                        label="Vial #684", lot="BATCH-684-VISIBLE")
            db.add(vial)
            db.commit()
            vid = vial.id
        response = client.get("/reconstitution-calculator")
        assert response.status_code == 200

    html = response.text
    assert 'id="recon-selected-vial684"' in html
    assert 'data-vendor="Recon684 Example Supplier"' in html
    assert 'data-lot="BATCH-684-VISIBLE"' in html
    # Real layout and script behavior. Never settle for metadata hidden in the DOM.
    css = __import__("pathlib").Path(__file__).resolve().parents[1].joinpath(
        "app/static/css/reconstitution-calculator.css"
    ).read_text()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width":width,"height":800},
                                    color_scheme=scheme)
            page.set_content(html, wait_until="domcontentloaded")
            page.add_style_tag(content=css)
            page.locator("#recon-vial-select").select_option(str(vid))
            detail = page.locator("#recon-selected-vial684")
            assert detail.is_visible()
            assert "Recon684 Example Supplier" in detail.inner_text()
            assert "BATCH-684-VISIBLE" in detail.inner_text()
            assert "Recon684 Blue Peptide" in detail.inner_text()
            assert "Vial #684" in detail.inner_text()
            for name in ("vendor", "lot"):
                node = page.locator("#recon-selected-" + name + "684")
                assert node.is_visible()
                rect = node.bounding_box()
                assert rect and rect["width"] > 0 and rect["height"] > 0
                assert rect["x"] + rect["width"] <= width + 1, rect
            assert page.evaluate(
                "() => document.documentElement.scrollWidth <= innerWidth + 1"
            )
            page.locator("#recon-vial-select").select_option("")
            assert detail.is_hidden()
        finally:
            browser.close()
