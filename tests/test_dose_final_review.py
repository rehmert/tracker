"""Read-only final review of dose form values."""

from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/doses.html"
SCRIPT = ROOT / "app/static/js/tracker-dose-final-review.js"
STYLE = ROOT / "app/static/css/tracker-dose-final-review.css"


def test_review_is_wired_before_submit():
    html = TEMPLATE.read_text()

    for marker in (
        'id="tracker-dose-final-review"',
        'id="tracker-dose-review-summary"',
        'id="tracker-dose-review-details"',
        "tracker-dose-final-review.js",
        "tracker-dose-final-review.css",
    ):
        assert html.count(marker) == 1, marker

    assert html.index('id="tracker-dose-final-review"') < (
        html.index('>Add to log</button>')
    )


def test_all_recorded_values_are_reviewed():
    text = SCRIPT.read_text()

    for name in (
        'value("kind")',
        'selectedLabel("vial_id")',
        'value("amount")',
        'value("unit")',
        'value("taken_at")',
        'selectedLabel("site")',
        'field("use_remaining")',
        'input[name="supply_id_used"]:checked',
    ):
        assert name in text, name


def test_review_is_read_only():
    text = SCRIPT.read_text()

    for forbidden in (
        "fetch(",
        "requestSubmit(",
        "form.submit(",
        "localStorage.",
        "sessionStorage.",
    ):
        assert forbidden not in text

    assert "description.textContent = content" in text
    assert "form.addEventListener" in text


def test_dose_server_protections_remain():
    text = (
        ROOT / "app/routers/doses.py"
    ).read_text()

    assert "idempotency.check(" in text
    assert "reserve_inventory_write" in text

    Environment().parse(TEMPLATE.read_text())
    assert STYLE.exists()
