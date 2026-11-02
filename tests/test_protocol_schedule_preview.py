"""Read-only next-projection protocol index and existing Dose Workspace handoff.

Fixtures use synthetic in-memory objects or tests/conftest.py's disposable DB.
No dose submissions or live inventory changes occur.
"""
from datetime import date, timedelta
from types import SimpleNamespace as NS
from uuid import uuid4
import html
import re
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db import SessionLocal
from app.models import Compound, Protocol, ProtocolItem, ProjectionExclusion
from app.protocol_schedule_preview import LOOKAHEAD_DAYS, preview


def row_item(*, cid=5, item_id=10, amount=2.5, period="week",
             count=1, dose_days="", time="08:00", start_week=1,
             end_week=None, pos=0):
    return NS(
        id=item_id, compound_id=cid, compound=NS(name="Example compound"),
        amount_value=amount, amount_unit="mg",
        freq_count=count, freq_period=period,
        dose_days=dose_days, dose_time=time,
        start_week=start_week, end_week=end_week, position=pos,
    )


def row_protocol(start, items, *, active=True, end=None):
    return NS(is_active=active, start_date=start, end_date=end, items=items)


def test_inactive_and_missing_start_have_no_next_projection():
    on = date(2026, 11, 2)
    item = row_item()
    assert preview(row_protocol(on, [item], active=False), on)["state"] == "what_if"
    assert preview(row_protocol(None, [item]), on)["state"] == "missing_start"


def test_ended_empty_and_far_future_are_labeled():
    on = date(2026, 11, 2)
    item = row_item()
    assert preview(row_protocol(on - timedelta(days=20), [item],
                                end=on - timedelta(days=1)), on)["state"] == "ended"
    assert preview(row_protocol(on, []), on)["state"] == "no_items"
    future = on + timedelta(days=LOOKAHEAD_DAYS + 1)
    assert preview(row_protocol(future, [item]), on)["state"] == "later"


def test_next_weekly_day_honors_saved_weekday_and_amount():
    on = date(2026, 11, 2)  # Monday
    item = row_item(count=1, period="week", dose_days="3", time="07:15")
    result = preview(row_protocol(on, [item]), on)
    event = result["next"]
    assert event["date"] == date(2026, 11, 5)  # Thursday
    assert event["time"] == "07:15"
    assert (event["compound_id"], event["amount"], event["unit"]) == (5, 2.5, "mg")


def test_escalation_uses_current_stage_not_old_dose():
    on = date(2026, 11, 9)
    start = date(2026, 11, 2)
    early = row_item(item_id=1, amount=2.5, start_week=1, end_week=1,
                     period="interval", count=7)
    late = row_item(item_id=2, amount=5, start_week=2,
                    period="interval", count=7)
    result = preview(row_protocol(start, [early, late]), on)
    assert result["next"]["date"] == on
    assert result["next"]["item_id"] == 2
    assert result["next"]["amount"] == 5


def test_hidden_once_skips_one_occurrence_but_not_future():
    on = date(2026, 11, 2)
    item = row_item(period="interval", count=7)
    rules = {10: [NS(scope="once", scheduled_on=on)]}
    event = preview(row_protocol(on, [item]), on, rules)["next"]
    assert event["date"] == on + timedelta(days=7)


def test_hidden_onward_does_not_claim_an_upcoming_projection():
    on = date(2026, 11, 2)
    item = row_item(period="interval", count=7)
    rules = {10: [NS(scope="onward", scheduled_on=on)]}
    result = preview(row_protocol(on, [item]), on, rules)
    assert result["state"] == "none_soon"
    assert result["next"] is None


def test_interval_84_hour_schedule_uses_calendar_clock():
    start = date(2026, 11, 2)
    item = row_item(period="interval", count=3.5, time="08:00")
    result = preview(row_protocol(start, [item]), date(2026, 11, 5))
    assert result["next"]["date"] == date(2026, 11, 5)
    assert result["next"]["time"] == "20:00"


def test_plan_end_date_and_lookahead_are_respected():
    start = date(2026, 11, 2)
    item = row_item(period="interval", count=7)
    result = preview(row_protocol(start, [item], end=start), start + timedelta(days=1))
    assert result["next"] is None
    monthly = row_item(period="interval", count=90)
    assert preview(row_protocol(start, [monthly]), start + timedelta(days=1))["state"] == "none_soon"


def test_earliest_event_wins_across_compounds():
    start = date(2026, 11, 2)
    first = row_item(cid=1, item_id=1, period="interval", count=8,
                     time="10:00", pos=0)
    second = row_item(cid=2, item_id=2, period="interval", count=7,
                      time="09:00", pos=1)
    result = preview(row_protocol(start, [first, second]), start + timedelta(days=1))
    assert result["next"]["date"] == start + timedelta(days=7)
    assert result["next"]["compound_id"] == 2


def test_protocol_table_links_to_workspace_and_exclusions_update_date():
    start = date.today()
    unique = str(uuid4())
    with TestClient(app, follow_redirects=False) as client:
        with SessionLocal() as db:
            compound = Compound(name="Next preview " + unique, category="peptide")
            protocol = Protocol(name="Preview schedule " + unique,
                                is_active=True, start_date=start)
            item = ProtocolItem(compound=compound, amount_value=1.25,
                                amount_unit="mg", freq_count=7,
                                freq_period="interval", start_week=1,
                                position=0, dose_time="09:30")
            protocol.items.append(item)
            db.add(protocol)
            db.commit()
            pid, item_id, cid = protocol.id, item.id, compound.id

        first = client.get("/protocols")
        assert first.status_code == 200
        # Exact row-specific destination, not the introduction or another plan.
        def planned_workspace_link(markup):
            links = re.findall(r'href="(/dose-workspace\?[^"]+)"', markup)
            for raw in links:
                url = html.unescape(raw)
                params = parse_qs(urlsplit(url).query)
                if params.get("compound_id") == [str(cid)]:
                    return url, params
            raise AssertionError("Expected the protocol's actual vial link")

        first_url, first_params = planned_workspace_link(first.text)
        assert first_params["planned_date"] == [start.isoformat()]
        assert first_params["planned_time"] == ["09:30"]
        assert first_params["planned_amount"] == ["1.25"]
        assert first_params["planned_unit"] == ["mg"]

        with SessionLocal() as db:
            db.add(ProjectionExclusion(protocol_item_id=item_id,
                                       scheduled_on=start,
                                       scope="once", reason="test hidden occurrence"))
            db.commit()
        after = client.get("/protocols")
        assert after.status_code == 200
        next_day = start + timedelta(days=7)
        next_url, next_params = planned_workspace_link(after.text)
        assert next_params["planned_date"] == [next_day.isoformat()]
        assert next_params["planned_time"] == ["09:30"]
        assert next_url != first_url

        # Verify the actual link is GET-only and the workspace renders.
        response = client.get(next_url)
        assert response.status_code == 200
        assert "Dose Workspace" in response.text
        assert "Recording a planned dose" in response.text


def test_protocol_table_keeps_existing_filter_column_contract():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    table = (root / "app/templates/protocols.html").read_text()
    js = (root / "app/static/js/tracker-protocol-dashboard-3494.js").read_text()
    assert "data-next-planned=" in table
    assert 'value="next-asc"' in table
    assert "case 'next-asc'" in js
    assert "row.cells[1]?.textContent" in js
    assert "row.cells[2]?.textContent" in js
    assert "Next planned (60 days)" in table
    assert 'colspan="6"' in table
