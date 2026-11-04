"""Dose final review includes notes and navigates all issues."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "app/static/js/tracker-dose-final-review.js"
HTML = ROOT / "app/templates/doses.html"
CSS = ROOT / "app/static/css/tracker-dose-final-review.css"


def test_notes_appear_in_review():
    script = JS.read_text()

    assert '["Notes", value("notes") || "No notes entered"]' in script
    assert "description.textContent = content" in script
    assert "description.innerHTML" not in script


def test_issue_navigation_cycles():
    script = JS.read_text()

    assert "let outstandingIssues = [];" in script
    assert "let issueIndex = 0;" in script
    assert "issueTargets.filter(Boolean)" in script
    assert "new Set(issueTargets.filter(Boolean))" in script
    assert "issueIndex = (issueIndex + 1) % outstandingIssues.length" in script
    assert "firstIssue = outstandingIssues[issueIndex]" in script
    assert '"Go to issue " + (issueIndex + 1)' in script


def test_editing_resets_issue_position():
    script = JS.read_text()

    assert "issueIndex = 0;" in script
    assert "firstIssue = outstandingIssues[0] || null" in script
    assert 'form.addEventListener("input", render)' in script
    assert 'form.addEventListener("change", render)' in script


def test_navigation_opens_disclosure_and_focuses():
    script = JS.read_text()

    assert 'firstIssue.closest("details")' in script
    assert "disclosure.open = true" in script
    assert "firstIssue.focus({preventScroll:true})" in script


def test_existing_review_works_and_remains_read_only():
    script = JS.read_text()
    html = HTML.read_text()

    assert "tracker-dose-final-review.js?v=20261103g" in html
    assert 'id="tracker-dose-review-first-issue"' in html
    assert "white-space: pre-wrap" in CSS.read_text()

    Environment().parse(html)

    for forbidden in (
        "fetch(",
        "requestSubmit(",
        "form.submit(",
        "localStorage.",
        "sessionStorage.",
    ):
        assert forbidden not in script


def test_backend_protections_preserved():
    source = (ROOT / "app/routers/doses.py").read_text()

    assert "idempotency.check(" in source
    assert "reserve_inventory_write" in source
    assert "manual_supplies.deduct(" in source
