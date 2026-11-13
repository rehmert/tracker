"""Release 599: dashboard-only visibility, horizon and title-case contracts.

HTTP fixtures use the isolated pytest database provided by tests/conftest.py.
"""
import re
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Compound, Protocol, ProtocolItem


def test_dashboard_excludes_what_if_and_shows_only_next_three_days():
    today = datetime.now().date()
    unique = uuid4().hex
    active_name = "R599 Active " + unique
    what_if_name = "R599 WhatIf " + unique
    with TestClient(app) as client:
        with SessionLocal() as db:
            compound = Compound(name="R599 Compound " + unique, category="peptide")
            active = Protocol(name=active_name, is_active=True, start_date=today)
            active.items.append(ProtocolItem(
                compound=compound, amount_value=1.0, amount_unit="mg",
                freq_count=1.0, freq_period="interval", start_week=1,
                position=0, dose_time="09:00",
            ))
            what_if = Protocol(name=what_if_name, is_active=False, start_date=today)
            db.add_all([active, what_if])
            db.commit()
            compound_id = compound.id

        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        current = re.search(
            r'<section\b[^>]*id="current-protocols"[^>]*>(.*?)</section>',
            html, re.S,
        )
        assert current is not None
        assert active_name in current.group(1)
        assert what_if_name not in current.group(1)
        assert "What-if</span>" not in current.group(1)
        assert what_if_name not in html
        assert "No active protocols." not in current.group(1)

        upcoming = re.search(
            r'<h3>Upcoming · next 3 days</h3>(.*?)</div>',
            html, re.S,
        )
        assert upcoming is not None
        assert "next 7 days" not in upcoming.group(1)
        projected = set(re.findall(
            r'/doses\?compound_id=' + str(compound_id) +
            r'&amp;planned_date=(\d{4}-\d{2}-\d{2})',
            upcoming.group(1),
        ))
        assert projected == {
            (today + timedelta(days=offset)).isoformat()
            for offset in (1, 2, 3)
        }
        assert "Next 3 days" in html
        assert "No projected administrations in the next 3 days." not in upcoming.group(1)

        # The full protocol management page still retains saved What-If plans.
        protocols_page = client.get("/protocols")
        assert protocols_page.status_code == 200
        assert what_if_name in protocols_page.text


def test_dashboard_only_changes_not_mobile_or_schedule_engine():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    router = (root / "app/routers/dashboard.py").read_text()
    page = (root / "app/templates/dashboard.html").read_text()
    engine = (root / "app/today.py").read_text()
    mobile = (root / "app/templates/mobile_today509.html").read_text()
    title_js = (root / "app/static/js/tracker-page-title-case.js").read_text()
    browser = (root / "tests/browser/test_strict_csrf521.py").read_text()

    assert "if not protocol.is_active:" in router
    assert "today_date + timedelta(days=3)" in router
    assert "dashboard_upcoming=dashboard_upcoming" in router
    assert "today_summary=today_summary" in router
    assert "dashboard_upcoming | length" in page
    assert "{% for day, e in dashboard_upcoming %}" in page
    assert "Upcoming · next 3 days" in page
    assert "Next 3 days" in page
    assert "No active protocols." in page
    assert "days_ahead: int = 7" in engine
    assert "Next 7 Days" in mobile
    assert r"return cased.replace(/(['’])S\b/g, '$1s');" in title_js
    assert "def test_599_dashboard_headings_http_https(" in browser
    assert '@pytest.mark.parametrize("scheme", ("http", "https"))' in browser
