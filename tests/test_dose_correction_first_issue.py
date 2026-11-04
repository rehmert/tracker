"""Correction review navigates to invalid quantity controls."""

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "app/static/js/tracker-dose-correction-review.js"
HTML = ROOT / "app/templates/dose_edit.html"
ROUTER = ROOT / "app/routers/doses.py"


def test_each_validation_issue_retains_input_reference():
    js = JS.read_text()

    assert "const issueControls = [];" in js
    assert js.count("issues.push(") == 3
    assert js.count("issueControls.push(input);") == 3


def test_jump_is_only_created_with_validation_issues():
    js = JS.read_text()

    assert "const firstIssueControl = issueControls[0];" in js
    assert "if (firstIssueControl) {" in js

    assert (
        js.index("const firstIssueControl = issueControls[0];")
        > js.index('summary.textContent =\n          issues.length')
    )


def test_jump_expands_details_and_focuses_quantity():
    js = JS.read_text()

    assert 'jump.type = "button";' in js
    assert (
        'jump.textContent = "Go to first quantity issue";'
        in js
    )
    assert 'jump.addEventListener("click", () => {' in js
    assert 'firstIssueControl.closest("details")' in js
    assert "if (section) section.open = true;" in js
    assert "firstIssueControl.focus();" in js
    assert "panel.appendChild(jump);" in js


def test_jump_does_not_auto_correct_or_submit():
    js = JS.read_text()

    for forbidden in (
        "requestSubmit(",
        "form.submit(",
        "fetch(",
        "localStorage.",
        "sessionStorage.",
    ):
        assert forbidden not in js


def test_existing_inventory_review_remains():
    js = JS.read_text()

    assert "qty > available + 1e-9" in js
    assert "Number.isInteger(qty)" in js
    assert "const remaining = available - corrected;" in js
    assert "const delta = original - corrected;" in js
    assert "movementCounts.returned += 1;" in js
    assert "movementCounts.consumed += 1;" in js
    assert "movementCounts.unchanged += 1;" in js


def test_template_and_backend_remain_compatible():
    html = HTML.read_text()
    router = ROUTER.read_text()

    assert "?v=20261104g" in html
    assert 'id="tracker-dose-correction-form"' in html
    assert 'id="tracker-dose-correction-review"' in html
    assert 'name="supply_qty_{{ s.id }}"' in html

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

    Environment().parse(html)
