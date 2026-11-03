"""Calendar productivity: month totals, search controls and safe handoffs."""
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from jinja2 import Environment

from app.main import app
from app.routers.calendar import calendar_status_counts


ROOT = Path(__file__).resolve().parents[1]


def test_month_counts_exclude_outside_grid_and_preserve_statuses():
    days = [
        {"in_month": True, "events": [
            {"status": "due"}, {"status": "upcoming"}, {"status": "recorded"},
            {"status": "unrecorded"}, {"status": "extra"}, {"status": "extra"}]},
        {"in_month": False, "events": [{"status": "due"}]},
        {"in_month": True, "events": [{"status": "upcoming"}]},
    ]
    counts = calendar_status_counts(days)
    assert counts == {
        "due": 1, "upcoming": 2, "unrecorded": 1,
        "recorded": 1, "extra": 2,
    }


def test_calendar_html_renders_workbench_and_today_link():
    with TestClient(app) as client:
        response = client.get("/calendar?month=2026-11")
    assert response.status_code == 200

    for marker in (
        'id="calendar-workbench"',
        'id="calendar-search"',
        'id="calendar-status-filter"',
        'id="calendar-reset-filters"',
        'id="calendar-jump-today"',
        'id="calendar-print"',
        'id="calendar-filter-summary"',
        'id="calendar-grid"',
        'tracker-calendar-workbench.js?v=20261103b',
        'tracker-calendar-workbench.css?v=20261103b',
        'Due and not logged',
        'Unmatched Logs',
    ):
        assert marker in response.text, marker

    assert 'name="month" value="2026-11"' in response.text


def test_event_controls_stay_inside_wrapped_activity():
    source = (ROOT / "app/templates/calendar.html").read_text()
    Environment().parse(source)

    assert 'data-calendar-status="{{ x.status }}"' in source
    assert 'data-calendar-search="' in source
    assert "data-calendar-date=" in source

    start = source.index('<div class="calendar-activity"')
    end = source.index('{% endfor %}', start)

    body = source[start:end]
    assert "Log this dose" in body
    assert "Choose vial first" in body
    assert 'action="/calendar/exclude"' in body


def test_existing_calendar_ical_export_untouched():
    with TestClient(app) as client:
        response = client.get("/calendar/export.ics?month=2026-11")
    assert response.status_code == 200
    assert "BEGIN:VCALENDAR" in response.text
    assert "END:VCALENDAR" in response.text


def test_status_filter_is_only_a_client_side_visibility_change():
    script = (
        ROOT / "app/static/js/tracker-calendar-workbench.js"
    ).read_text()

    assert "item.hidden = !show" in script
    assert "status === 'due'" in script
    assert "status === 'unrecorded'" in script
    assert "window.print" in script
    assert "fetch(" not in script
    assert "form.submit" not in script
