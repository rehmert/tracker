"""Each correction issue links to its corresponding quantity input."""

from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "app/static/js/tracker-dose-correction-review.js"
HTML = ROOT / "app/templates/dose_edit.html"
ROUTER = ROOT / "app/routers/doses.py"


def test_all_three_error_types_track_their_inputs():
    js = JS.read_text()
    assert js.count("issues.push(") == 3
    assert js.count("issueControls.push(input);") == 3


def test_each_issue_has_individual_focus_control():
    js = JS.read_text()
    required = (
        "issues.forEach((issue, index) => {",
        "const target = issueControls[index];",
        'jump.textContent = "Go to quantity field";',
        'jump.type = "button";',
        'jump.addEventListener("click", () => {',
        'const section = target.closest("details");',
        "if (section) section.open = true;",
        "target.focus();",
        "entry.appendChild(jump);",
        "list.appendChild(entry);",
    )
    for marker in required:
        assert marker in js, marker


def test_first_issue_control_still_available():
    js = JS.read_text()
    assert "const firstIssueControl = issueControls[0];" in js
    assert 'jump.textContent = "Go to first quantity issue";' in js
    assert "firstIssueControl.focus();" in js


def test_navigation_does_not_submit_or_mutate_inventory():
    js = JS.read_text()
    assert "entry.textContent = issue;" in js
    assert "item.textContent = projection;" in js

    for forbidden in (
        "fetch(",
        "requestSubmit(",
        "form.submit(",
        "localStorage.",
        "sessionStorage.",
    ):
        assert forbidden not in js


def test_inventory_review_and_template_remain():
    js = JS.read_text()
    html = HTML.read_text()

    assert "qty > available + 1e-9" in js
    assert "Number.isInteger(qty)" in js
    assert "const delta = original - corrected;" in js
    assert "movementCounts.returned += 1;" in js
    assert "?v=20261104g" in html
    assert 'id="tracker-dose-correction-review"' in html
    Environment().parse(html)


def test_backend_inventory_and_audit_unchanged():
    router = ROUTER.read_text()
    post = router.split(
        '@router.post("/doses/{did}/edit")', 1
    )[1].split(
        '@router.get("/dose-workspace")', 1
    )[0]

    assert "reserve_inventory_write" in post
    assert "manual_supplies.selections(" in post
    assert "credits={u.supply_id:u.amount" in post
    assert 'action="edit"' in post
    assert "db.commit()" in post
