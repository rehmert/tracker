"""Release 73-76: inventory, lab and library contracts."""
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment

from app.pk_inventory_events import allocate_events

ROOT=Path(__file__).resolve().parents[1]


def vial(remaining,expiry=None):
    return {
        "remaining_mg":remaining,
        "expires_on":expiry,
        "beyond_use_on":None,
        "closed_on":None,
        "status":"sealed",
    }


def test_event_ledger_tracks_allocation_and_shortage():
    rows=allocate_events(
        [vial(5)],
        [
            (datetime(2026,11,5,9),3),
            (datetime(2026,11,6,9),4),
        ],
        date(2026,11,4),
        date(2026,11,30),
    )
    ledger=rows["forecast_events"]
    assert len(ledger)==2
    assert ledger[0]["allocated_mg"]==3
    assert ledger[0]["remaining_usable_mg"]==2
    assert ledger[1]["allocated_mg"]==2
    assert ledger[1]["unfilled_mg"]==2
    assert rows["first_shortage_date"]=="2026-11-06"
    assert rows["total_unfilled_mg"]==2


def test_ledger_respects_future_expiration():
    rows=allocate_events(
        [vial(5,date(2026,11,5))],
        [(datetime(2026,11,6,9),3)],
        date(2026,11,4),
        date(2026,11,30),
    )
    assert rows["forecast_events"][0]["allocated_mg"]==0
    assert rows["forecast_events"][0]["unfilled_mg"]==3


def test_ledger_does_not_modify_input_stock():
    stock=[vial(5)]
    allocate_events(
        stock,[(datetime(2026,11,5,9),2)],
        date(2026,11,4),
        date(2026,11,30),
    )
    assert stock[0]["remaining_mg"]==5


def test_workbench_asset_and_ui_contracts():
    html=(
        ROOT/"app/templates/protocol_edit.html"
    ).read_text()
    js=(
        ROOT/"app/static/js/tracker-pk-workbench.js"
    ).read_text()
    library=(
        ROOT/"app/static/js/tracker-pk-library.js"
    ).read_text()

    assert 'id="pkExpSearch"' in html
    assert 'id="pkExpSort"' in html
    assert "tracker-pk-library.js?v=bundle84" in html
    assert "tracker-pk-workbench.js?v=bundle84" in html
    assert "function renderList(preferred)" in library
    assert "forecast_events" in js
    assert "days_since_scheduled_dose" in js
    Environment().parse(html)


def test_no_new_medical_record_writes():
    code=(
        ROOT/"app/pk_inventory_events.py"
    ).read_text()
    for operation in (
        "db.commit(", "db.add(", "db.delete(",
        "db.flush("
    ):
        assert operation not in code
