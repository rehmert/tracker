"""Read-only selection of an existing lab layout."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.routers import labs as labs_router
from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


def test_form_offers_recent_reports(monkeypatch):
    reports = [
        SimpleNamespace(
            id=13,
            drawn_on="2026-10-20",
            lab_name="Recent report",
            results=[],
        ),
        SimpleNamespace(
            id=12,
            drawn_on="2026-09-20",
            lab_name="Older report",
            results=[],
        ),
    ]

    db = MagicMock()
    db.scalars.return_value = reports

    captured = {}

    def fake_render(request, name, **kwargs):
        captured.update(kwargs)
        return kwargs

    monkeypatch.setattr(labs_router, "render", fake_render)
    monkeypatch.setattr(
        labs_router,
        "_name_options",
        lambda db: ["TSH", "Free T4"],
    )

    request = SimpleNamespace(query_params={})

    result = labs_router._form(
        request,
        db,
        copied_from=reports[0],
    )

    assert result["source_reports"] == reports
    assert result["copied_from"] is reports[0]
    assert result["names"] == ["TSH", "Free T4"]
    assert len(result["rows"]) == 3
    assert captured == result

    assert db.scalars.call_count == 1
    query = db.scalars.call_args.args[0]
    assert "LIMIT" in str(query.compile()).upper()


def test_get_only_source_picker():
    html = read("app/templates/lab_form.html")

    for token in (
        'method="get" action="/labs/new"',
        'name="copy_from"',
        'id="lab-source-report"',
        "source_reports",
        "copied_from.id == r.id",
        "r.results|length",
        "Use This Layout",
        'href="/labs/new"',
    ):
        assert token in html


def test_existing_forms_and_reviews_unchanged():
    html = read("app/templates/lab_form.html")

    for token in (
        'action="/labs/import-csv"',
        'action="/labs"',
        "data-lab-csv-entry",
        "data-lab-manual-entry",
        "data-lab-entry-review",
        "data-lab-duplicate-warning",
        'id="lab-rows"',
        "tracker-lab-entry-safeguards.js",
    ):
        assert token in html


def test_prior_results_are_not_copied():
    router = read("app/routers/labs.py")

    assert 'value=""' in router
    assert 'ref_low=""' in router
    assert 'ref_high=""' in router
    assert "copied_from=previous" in router


def test_templates_parse():
    templates.env.get_template("lab_form.html")
    templates.env.get_template("labs.html")
    templates.env.get_template("lab_report.html")
