"""Focused regression contracts for Release 69–72."""
from datetime import date,datetime
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment

from app.pk_inventory_events import allocate_events

ROOT=Path(__file__).resolve().parents[1]


def test_expired_vial_cannot_cover_future_event():
    stock=[{
        "remaining_mg":10,
        "expires_on":date(2026,11,5),
        "beyond_use_on":None,
        "closed_on":None,
        "status":"sealed",
    }]
    events=[
        (datetime(2026,11,6,9),5)
    ]
    result=allocate_events(
        stock,events,
        date(2026,11,4),date(2026,12,4)
    )
    assert result["starting_usable_mg"]==10
    assert result["first_shortage_date"]=="2026-11-06"
    assert result["expiring_during_window_mg"]==10


def test_fefo_uses_earlier_expiration_first():
    stock=[
        {
            "remaining_mg":5,
            "expires_on":date(2026,11,10),
            "beyond_use_on":None,
            "closed_on":None,
            "status":"sealed",
        },
        {
            "remaining_mg":5,
            "expires_on":date(2026,11,30),
            "beyond_use_on":None,
            "closed_on":None,
            "status":"sealed",
        },
    ]
    events=[
        (datetime(2026,11,8,9),5),
        (datetime(2026,11,20,9),5),
    ]
    result=allocate_events(
        stock,events,
        date(2026,11,4),date(2026,12,4)
    )
    assert result["first_shortage_date"] is None
    assert result["demand_mg"]==10
    assert result["remaining_after_allocation_mg"]==0


def test_inventory_does_not_mutate_original_stock():
    records=[{
        "remaining_mg":5,
        "expires_on":None,
        "beyond_use_on":None,
        "closed_on":None,
        "status":"in_use",
    }]
    allocate_events(
        records,[(datetime(2026,11,6,9),3)],
        date(2026,11,4),date(2026,12,4)
    )
    assert records[0]["remaining_mg"]==5


def test_lab_and_library_assets():
    html=(
        ROOT/"app/templates/protocol_edit.html"
    ).read_text()
    lab=(
        ROOT/"app/static/js/tracker-pk-lab-trends.js"
    ).read_text()
    lib=(
        ROOT/"app/static/js/tracker-pk-library.js"
    ).read_text()

    assert "tracker-pk-lab-trends.js?v=bundle72" in html
    assert "tracker-pk-library.js?v=bundle72" in html
    assert 'id="pkExpNotes"' in html
    assert 'data-source-updated="' in html
    assert "No PK curve is fitted" in lab
    assert "function doseEdits()" in lib
    assert "source_updated_at" in lib

    Environment().parse(html)


def test_backend_uses_vial_aware_forecast():
    code=(
        ROOT/"app/pk_workbench.py"
    ).read_text()
    assert "forecast_inventory(" in code
    assert "competing_demand(" not in code
    assert "db.commit(" not in code
    assert "db.add(" not in code
