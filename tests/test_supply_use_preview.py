"""Supply usage preview is read-only and scoped."""

from pathlib import Path

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


def test_assets_registered():
    html = read("app/templates/supplies.html")

    assert "tracker-supply-use-preview.js" in html
    assert "tracker-supply-use-preview.css" in html
    assert "data-tracker-supply-use" in html
    assert 'data-remaining="{{ s.remaining_qty }}"' in html
    assert 'name="submission_token"' in html


def test_usage_preview_and_validation():
    js = read(
        "app/static/js/tracker-supply-use-preview.js"
    )

    for token in (
        "After use:",
        "Insufficient stock:",
        "quantity > remaining",
        "Number.isFinite",
        "setCustomValidity",
        "reportValidity()",
        "submitting = true",
        "pageshow",
    ):
        assert token in js


def test_no_extra_network_or_storage():
    js = read(
        "app/static/js/tracker-supply-use-preview.js"
    )

    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
    ):
        assert forbidden not in js


def test_template_parses():
    templates.env.get_template("supplies.html")
