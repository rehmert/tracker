"""Future timestamps are highlighted in read-only dose review."""

from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]

JS = ROOT / "app/static/js/tracker-dose-final-review.js"
HTML = ROOT / "app/templates/doses.html"
CSS = ROOT / "app/static/css/tracker-dose-final-review.css"


def test_local_datetime_regex_is_correct():
    script = JS.read_text()

    expected_regex = (
        r'/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/'
    )

    assert expected_regex in script
    assert "const validLocalTime =" in script
    assert "new Date(when)" in script
    assert "Number.isFinite(parsedTime.getTime())" in script
    assert "Date.now() + 60000" in script


def test_future_timestamp_is_review_issue():
    script = JS.read_text()

    assert "if (futureTime)" in script
    assert "timestamp is in the future" in script
    assert (
        'futureTime ? field("taken_at") : null'
        in script
    )
    assert "new Set(issueTargets.filter(Boolean))" in script


def test_future_timestamp_warning_styling():
    script = JS.read_text()
    css = CSS.read_text()

    assert (
        "panel.dataset.futureTimestamp = futureTime"
        in script
    )
    assert 'data-future-timestamp="true"' in css


def test_review_remains_read_only():
    script = JS.read_text()

    for forbidden in (
        "fetch(",
        "requestSubmit(",
        "form.submit(",
        "localStorage.",
        "sessionStorage.",
    ):
        assert forbidden not in script

    assert "description.textContent = content" in script


def test_template_and_backend_safeguards():
    template = HTML.read_text()

    assert (
        "tracker-dose-final-review.js?v=20261103g"
        in template
    )
    assert 'name="taken_at"' in template
    assert 'id="tracker-dose-review-first-issue"' in template

    Environment().parse(template)

    backend = (
        ROOT / "app/routers/doses.py"
    ).read_text()

    assert "idempotency.check(" in backend
    assert "reserve_inventory_write" in backend
    assert "manual_supplies.deduct(" in backend
