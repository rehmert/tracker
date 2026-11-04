"""Calendar navigation is read-only and respects active filters."""

from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]

TEMPLATE = ROOT / "app/templates/calendar.html"

SCRIPT = (
    ROOT / "app/static/js/tracker-calendar-day-navigation.js"
)

STYLE = (
    ROOT / "app/static/css/tracker-calendar-day-navigation.css"
)


def test_navigation_controls_and_assets():
    html = TEMPLATE.read_text()

    for marker in (
        'id="calendar-matching-day-navigation"',
        'id="calendar-previous-matching-day"',
        'id="calendar-next-matching-day"',
        'id="calendar-matching-day-status"',
        "tracker-calendar-day-navigation.js",
        "tracker-calendar-day-navigation.css",
    ):
        assert html.count(marker) == 1


def test_navigation_counts_visible_days_only():
    script = SCRIPT.read_text()

    assert '.filter(day => !day.classList.contains("outside"))' in script
    assert '.some(item => !item.hidden)' in script
    assert "window.location.hash = target.id" in script


def test_navigation_respects_filters():
    script = SCRIPT.read_text()

    assert 'search.addEventListener("input", update)' in script
    assert 'filter.addEventListener("change", update)' in script
    assert "queueMicrotask(update)" in script
    assert 'window.addEventListener("hashchange", update)' in script


def test_navigation_does_not_mutate_records():
    script = SCRIPT.read_text()

    for forbidden in (
        "fetch(",
        "requestSubmit(",
        "form.submit(",
        "localStorage.",
        "sessionStorage.",
    ):
        assert forbidden not in script


def test_calendar_and_agenda_keep_status_metadata():
    html = TEMPLATE.read_text()

    assert html.count(
        'data-calendar-status="{{ x.status }}"'
    ) == 2

    assert 'id="calendar-day-{{ d.date.isoformat() }}"' in html
    assert "tracker-calendar-day-context.js" in html

    assert STYLE.exists()


def test_template_and_dose_safety():
    Environment().parse(TEMPLATE.read_text())

    server = (
        ROOT / "app/routers/doses.py"
    ).read_text()

    assert "idempotency.check(" in server
    assert "reserve_inventory_write" in server
