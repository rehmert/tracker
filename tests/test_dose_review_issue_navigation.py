"""Review navigation focuses incomplete fields without modifying records."""

from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "app/templates/doses.html"
JS = ROOT / "app/static/js/tracker-dose-final-review.js"
CSS = ROOT / "app/static/css/tracker-dose-final-review.css"


def test_issue_navigation_button():
    html = HTML.read_text()

    assert html.count(
        'id="tracker-dose-review-first-issue"'
    ) == 1

    assert html.index(
        'id="tracker-dose-review-first-issue"'
    ) < html.index('>Add to log</button>')

    assert "tracker-dose-final-review.js?v=20261103f" in html


def test_issue_targets():
    script = JS.read_text()

    for marker in (
        'invalidSupplies.map(item => item.input)',
        'field("vial_id")',
        'field("taken_at")',
        'field("amount")',
        'firstIssueButton.disabled = !firstIssue',
    ):
        assert marker in script, marker


def test_disclosure_and_focus():
    script = JS.read_text()

    assert 'firstIssue.closest("details")' in script
    assert "disclosure.open = true" in script
    assert "firstIssue.scrollIntoView(" in script
    assert "firstIssue.focus({preventScroll:true})" in script


def test_navigation_is_read_only():
    script = JS.read_text()

    for forbidden in (
        "fetch(",
        "requestSubmit(",
        "form.submit(",
        "localStorage.",
        "sessionStorage.",
    ):
        assert forbidden not in script

    assert 'firstIssueButton.addEventListener("click"' in script
    assert "description.textContent = content" in script


def test_server_safety_and_template():
    Environment().parse(HTML.read_text())
    assert CSS.exists()

    server = (
        ROOT / "app/routers/doses.py"
    ).read_text()

    assert "idempotency.check(" in server
    assert "reserve_inventory_write" in server
    assert "manual_supplies.deduct(" in server
