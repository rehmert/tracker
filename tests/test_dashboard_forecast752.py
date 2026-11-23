"""Release 752: complete per-protocol forecasts and permanent CSRF helper."""
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace as S
import subprocess
import pytest
from jinja2 import Environment
from app.dashboard_forecast752 import build_dashboard_forecasts752, weekly_base752

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 11, 23)


def item(cid=1, name="Test compound", amount=10, unit="mg",
         count=1, period="week", start_week=1, end_week=None):
    return S(compound_id=cid, compound=S(name=name), amount_value=amount,
             amount_unit=unit, freq_count=count, freq_period=period,
             start_week=start_week, end_week=end_week)


def p(pid, name, items=None, active=True, start=TODAY, end=None):
    return S(id=pid, name=name, is_active=active,
             items=[item()] if items is None else items,
             start_date=start, end_date=end)


def test_752_all_active_protocols_include_unstocked_and_shared_use():
    protocols = [
        p(1, "A", [item(amount=20)]), p(2, "B", [item(amount=15)]),
        p(3, "No vials", [item(cid=2, name="Other", amount=2, unit="IU", period="day")]),
        p(4, "Inactive", [item(amount=1000)], active=False),
    ]
    rows, low, watch = build_dashboard_forecasts752(
        protocols, {1: {"mass": 100000.0}}, TODAY)
    assert {r["protocol"] for r in rows} == {"A", "B", "No vials"}
    a, b = [r for r in rows if r["compound_id"] == 1]
    assert a["days_left"] == pytest.approx(20)
    assert b["days_left"] == pytest.approx(20)
    assert all(r["low"] and r["status"] == "Low stock" for r in (a, b))
    assert len(low) == 2 and len(watch) == 2
    assert sum(r["compound_id"] == 1 for r in low) == 1
    no_stock = next(r for r in rows if r["protocol"] == "No vials")
    assert no_stock["remaining"] == no_stock["days_left"] == 0
    assert no_stock["depletion"] == TODAY and no_stock["status"] == "No stock"


def test_752_future_ended_missing_start_and_empty_have_no_invented_depletion():
    protocols = [
        p(1, "Missing start", [item()], start=None),
        p(2, "Future start", [item()], start=TODAY + timedelta(days=5)),
        p(3, "Future stage", [item(start_week=3)]),
        p(4, "Completed stage", [item(end_week=1)],
          start=TODAY-timedelta(days=10)),
        p(5, "Ended", [item()], end=TODAY-timedelta(days=1)),
        p(6, "Empty", []),
    ]
    rows, low, watch = build_dashboard_forecasts752(
        protocols, {1: {"mass": 100000.0}}, TODAY)
    assert {r["protocol"]: r["status"] for r in rows} == {
        "Missing start": "Set start date",
        "Future start": "Not started",
        "Future stage": "Upcoming stage",
        "Completed stage": "Stage completed",
        "Ended": "Protocol ended",
        "Empty": "No compounds",
    }
    assert all(r["days_left"] is None and r["depletion"] is None for r in rows)
    assert not low and not watch


def test_752_only_current_stages_contribute_to_demand():
    rows, low, watch = build_dashboard_forecasts752([
        p(1, "Current", [item(amount=10)]),
        p(2, "Upcoming", [item(amount=100, start_week=2)]),
    ], {1: {"mass": 30000}}, TODAY)
    cur = next(r for r in rows if r["protocol"] == "Current")
    nxt = next(r for r in rows if r["protocol"] == "Upcoming")
    assert cur["days_left"] == pytest.approx(21)
    assert not cur["low"] and not low and len(watch) == 1
    assert nxt["days_left"] is None and nxt["status"] == "Upcoming stage"


def test_752_intervals_units_and_invalid_rate():
    assert weekly_base752(item(amount=3, unit="mg",
                               count=3, period="interval")) == ("mass", 7000.0)
    rows, _, _ = build_dashboard_forecasts752([
        p(1, "Mass", [item(amount=3, count=3, period="interval")]),
        p(2, "IU", [item(amount=2, unit="IU", period="day")]),
        p(3, "Bad unit", [item(unit="bogus")]),
        p(4, "Bad schedule", [item(count=0)]),
    ], {1: {"mass": 7000, "iu": 28}}, TODAY)
    out = {r["protocol"]: r for r in rows}
    assert out["Mass"]["days_left"] == pytest.approx(7)
    assert out["IU"]["days_left"] == pytest.approx(14)
    assert out["Bad unit"]["status"] == "Invalid unit"
    assert out["Bad schedule"]["status"] == "Invalid schedule"
    assert out["Bad unit"]["days_left"] is None
    assert out["Bad schedule"]["days_left"] is None


def test_752_dashboard_route_and_template_contract():
    router = (ROOT / "app/routers/dashboard.py").read_text()
    template = (ROOT / "app/templates/dashboard.html").read_text()
    Environment().parse(template)
    for marker in ("build_dashboard_forecasts752(protocols, inventory_dims",
                   "low_forecasts=low_forecasts",
                   "inventory_watch_forecasts=inventory_watch_forecasts"):
        assert marker in router
    for marker in ("<th>Protocol</th><th>Compound</th>",
                   '<a href="/protocols/{{ row.protocol_id }}">',
                   "row.days_left is not none", "low_forecasts | length",
                   "{% if inventory_watch_forecasts %}"):
        assert marker in template


def test_752_permanent_csrf_helper_is_auth_aware_and_bounded():
    helper = (ROOT / "scripts/tracker-csrf-dev751.sh").read_text()
    for marker in ("class NoRedirect(HTTPRedirectHandler)",
                   'parse_qs(redirect.query).get("next")',
                   "range(45)", "time.sleep(1)",
                   "Tracker did not become ready after restart",
                   "ROLLBACK_751=RESTORING_REPORT_ONLY",
                   "HTTP_751_UNSIGNED_WRITE=DENIED",
                   "TRACKER_CSRF_ENFORCE=1",
                   "systemctl restart tracker.service"):
        assert marker in helper, marker
    assert "git reset --hard" not in helper
    result = subprocess.run(["bash", "-n", str(ROOT / "scripts/tracker-csrf-dev751.sh")],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_752_real_dashboard_renders_unstocked_active_protocol():
    """A disposable real app/database must show demand without any vials."""
    from uuid import uuid4
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db import SessionLocal
    from app.models import Compound, Protocol, ProtocolItem

    unique = uuid4().hex[:10]
    protocol_name = "Forecast Plan " + unique
    compound_name = "Forecast Compound " + unique
    with TestClient(app) as client:
        with SessionLocal() as db:
            compound = Compound(name=compound_name, category="peptide")
            db.add(compound)
            db.flush()
            plan = Protocol(
                name=protocol_name, is_active=True,
                start_date=date.today() - timedelta(days=2),
            )
            db.add(plan)
            db.flush()
            db.add(ProtocolItem(
                protocol_id=plan.id, compound_id=compound.id,
                amount_value=1.0, amount_unit="mg",
                freq_count=1.0, freq_period="day",
                start_week=1,
            ))
            db.commit()
            plan_id = plan.id

        response = client.get("/", follow_redirects=False)
        assert response.status_code == 200
        markup = response.text
        assert "Inventory forecast" in markup
        assert protocol_name in markup
        assert compound_name in markup
        assert 'href="/protocols/' + str(plan_id) + '"' in markup
        assert "No stock" in markup
