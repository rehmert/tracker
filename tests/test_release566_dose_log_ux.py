"""Release 566: Dose Log IDs, timestamp layout, and calendar fallback.

These tests use disposable test data and never record a real administration.
"""
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.routers.doses import _select_dose_vial
from tests.test_calendar_auto_vial import _seed

ROOT = Path(__file__).resolve().parents[1]


def _vial(ident, compound, status):
    return SimpleNamespace(id=ident, compound_id=compound, status=status)


def _view(remaining, conc=250000):
    # Stored mass is mcg; this models an injectable 250 mg/mL product.
    return SimpleNamespace(
        remaining_base=remaining, dim="mass", conc_per_ml=conc,
    )


def test_testosterone_calendar_prefers_eligible_opened_vial():
    vials = [
        _vial(4, 7, "sealed"),
        _vial(31, 7, "in_use"),
        _vial(25, 7, "in_use"),
        _vial(1, 8, "in_use"),
    ]
    views = {
        4: _view(2000000), 31: _view(500000),
        25: _view(100000), 1: _view(500000),
    }
    selected, notice = _select_dose_vial(
        vials, views, 7, None, "2026-11-12", 50, "mg",
    )
    assert selected == 25  # Lowest-ID eligible opened vial, not unopened #4.
    assert "in-use vial" in notice

    # An explicitly selected matching vial remains respected.
    selected, _ = _select_dose_vial(
        vials, views, 7, 4, "2026-11-12", 50, "mg",
    )
    assert selected == 4


def test_calendar_falls_back_to_lowest_index_unopened_that_can_supply_dose():
    vials = [
        _vial(30, 7, "sealed"),
        _vial(20, 7, "sealed"),
        _vial(11, 7, "in_use"),
        _vial(5, 8, "sealed"),
        _vial(19, 7, "sealed"),
    ]
    views = {
        30: _view(200000), 20: _view(60000),
        11: _view(30000), 5: _view(500000),
        19: _view(45000),
    }
    selected, notice = _select_dose_vial(
        vials, views, 7, None, "2026-11-12", 50, "mg",
    )
    assert selected == 20
    assert "Lowest-index eligible unopened vial #20" in notice

    # If an opened vial can supply the same planned dose, prefer it.
    views[11] = _view(100000)
    assert _select_dose_vial(
        vials, views, 7, None, "2026-11-12", 50, "mg",
    )[0] == 11

    # A liquid-volume calendar entry must fit the vial's actual concentration.
    views[11] = _view(30000)
    assert _select_dose_vial(
        vials, views, 7, None, "2026-11-12", 0.2, "mL",
    )[0] == 20

    # Missing concentration cannot silently make a volume dose eligible.
    for ident in views:
        views[ident] = _view(views[ident].remaining_base, conc=None)
    selected, notice = _select_dose_vial(
        vials, views, 7, None, "2026-11-12", 0.2, "mL",
    )
    assert selected is None
    assert "Choose a vial manually" in notice


def test_vial_id_and_full_width_time_controls_present_in_dose_log():
    cid, ids, other = _seed()
    with TestClient(app) as client:
        result = client.get("/doses")
        assert result.status_code == 200
        html = result.text
        # Permanent vial identity is displayed even when the label exists.
        for ident in ids:
            assert f" · #{ident}" in html
        assert f" · #{other}" in html
        assert 'class="field wide tracker-dose-when-field"' in html
        assert "tracker-mobile-log373.css?v=566" in html

        planned = client.get(
            f"/doses?compound_id={cid}&planned_date=2026-11-12"
            "&planned_amount=50&planned_unit=mg"
        )
        assert planned.status_code == 200
        assert f" · #{other}" not in planned.text

    css = (ROOT / "app/static/css/tracker-mobile-log373.css").read_text()
    assert 'form[hx-post="/doses"] .tracker-dose-when-field' in css
    assert "grid-column: 1 / -1" in css
    assert "tracker-dose-when-field .tracker-time24-controls" in css
    assert "tracker-dose-when-field .tracker-time24-now" in css
    assert "grid-column: 1 / -1" in css
