"""Lab report layout reuse must never copy results."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import labs as labs_router
from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


class FakeDB:
    def __init__(self, report):
        self.report = report

    def get(self, model, identity):
        return self.report


def test_only_names_and_units_are_reused(monkeypatch):
    old_result = SimpleNamespace(
        analyte="TSH",
        value=0.01,
        unit="mIU/L",
        ref_low=0.4,
        ref_high=4.0,
        note="Previous measurement",
    )

    report = SimpleNamespace(
        id=23,
        drawn_on="2026-10-01",
        lab_name="Example",
        results=[
            old_result,
            SimpleNamespace(
                analyte="Free T4",
                value=2.5,
                unit="ng/dL",
                ref_low=0.8,
                ref_high=1.8,
                note="Previous note",
            ),
        ],
    )

    monkeypatch.setattr(
        labs_router,
        "_form",
        lambda request, db, **kw: kw,
    )

    result = labs_router.new_report(
        request=object(),
        copy_from=23,
        db=FakeDB(report),
    )

    assert result["copied_from"] is report
    assert result["rows"] == [
        dict(
            analyte="TSH", value="",
            unit="mIU/L", ref_low="", ref_high=""
        ),
        dict(
            analyte="Free T4", value="",
            unit="ng/dL", ref_low="", ref_high=""
        ),
    ]

    assert old_result.value == 0.01
    assert old_result.ref_low == 0.4


def test_missing_source_returns_404():
    with pytest.raises(HTTPException) as exc:
        labs_router.new_report(
            request=object(),
            copy_from=999999,
            db=FakeDB(None),
        )

    assert exc.value.status_code == 404


def test_ordinary_new_report_unchanged(monkeypatch):
    monkeypatch.setattr(
        labs_router,
        "_form",
        lambda request, db, **kw: kw,
    )

    result = labs_router.new_report(
        request=object(),
        copy_from=None,
        db=FakeDB(None),
    )

    assert result == {}


def test_source_links_and_form_safeguards():
    index = read("app/templates/labs.html")
    report = read("app/templates/lab_report.html")
    form = read("app/templates/lab_form.html")

    assert "/labs/new?copy_from={{ reports[0].id }}" in index
    assert "/labs/new?copy_from={{ rep.id }}" in report

    for marker in (
        "Only analyte names and units are prefilled.",
        "data-lab-manual-entry",
        "data-lab-csv-entry",
        "data-lab-entry-review",
        "data-lab-duplicate-warning",
        "tracker-lab-entry-safeguards.js",
        'action="/labs/import-csv"',
        'action="/labs"',
    ):
        assert marker in form


def test_templates_parse():
    for name in (
        "labs.html",
        "lab_form.html",
        "lab_report.html",
    ):
        templates.env.get_template(name)
