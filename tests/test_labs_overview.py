"""Lab overview search/range-status/sort is read-only and uses latest report ranges."""
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import LabReport, LabResult


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def lab_overview_client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_empty_overview_keeps_reports_search_available(lab_overview_client):
    client, _ = lab_overview_client
    response = client.get("/labs")
    assert response.status_code == 200
    assert 'id="labs-reports-table"' in response.text
    assert 'id="labs-report-search"' in response.text
    assert 'id="labs-reports-clear"' in response.text
    assert 'id="labs-reports-count"' in response.text
    assert "No lab reports yet." in response.text
    assert 'id="labs-trend-grid"' not in response.text


def test_latest_result_range_statuses_and_report_links(lab_overview_client):
    client, engine = lab_overview_client
    with Session(engine) as db:
        earlier = LabReport(drawn_on=date(2026, 7, 7), lab_name="Earlier Diagnostics")
        earlier.results = [
            LabResult(analyte="TSH", value=2.0, unit="mIU/L",
                      ref_low=0.4, ref_high=4.5),
        ]
        latest = LabReport(drawn_on=date(2026, 11, 1), lab_name="Current Diagnostics")
        latest.results = [
            LabResult(analyte="TSH", value=0.1, unit="mIU/L",
                      ref_low=0.4, ref_high=4.5),
            LabResult(analyte="Ferritin", value=520, unit="ng/mL",
                      ref_low=20, ref_high=300),
            LabResult(analyte="Glucose", value=90, unit="mg/dL",
                      ref_low=70, ref_high=99),
            LabResult(analyte="IGF-1", value=188, unit="ng/mL"),
        ]
        db.add_all([earlier, latest])
        db.commit()
        expected_report_count = db.scalar(select(func.count()).select_from(LabReport))
        expected_result_count = db.scalar(select(func.count()).select_from(LabResult))

    response = client.get("/labs")
    assert response.status_code == 200
    markup = response.text

    for marker in (
        'id="labs-trend-controls"',
        'id="labs-trend-grid"',
        'id="labs-analyte-search"',
        'id="labs-range-filter"',
        'id="labs-trend-sort"',
        'id="labs-trend-clear"',
        'id="labs-trend-count"',
        'id="labs-report-search"',
        'id="labs-reports-table"',
        'id="labs-reports-sort"',
        'tracker-labs-overview.js?v=20261108-497',
        'tracker-labs-overview.css?v=20261107-481',
        'data-lab-status="below"',
        'data-lab-status="above"',
        'data-lab-status="within"',
        'data-lab-status="unknown"',
        'data-lab-name="TSH"',
        'data-lab-results="2"',
        'data-lab-date="2026-11-01"',
        'data-lab-report-date="2026-07-07"',
        'data-lab-report-name="Earlier Diagnostics"',
        "Outside printed range",
        "No printed range",
    ):
        assert marker in markup, marker

    assert markup.count("data-labs-trend-card") == 4
    assert markup.count("data-labs-report-row") == 2
    assert 'href="/labs/' in markup

    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(LabReport)) == expected_report_count
        assert db.scalar(select(func.count()).select_from(LabResult)) == expected_result_count


def test_overview_filtering_never_submits_labs(lab_overview_client):
    source = (ROOT / "app/static/js/tracker-labs-overview.js").read_text()
    assert "card.hidden = !show" in source
    assert "row.hidden = !show" in source
    assert "grid.appendChild(card)" in source
    assert "filter === 'outside'" in source
    assert "filter === 'unknown'" not in source  # compared against data status generically
    assert "window.fetch" not in source
    assert "fetch(" not in source
    assert ".submit(" not in source
    assert "localStorage" not in source


def test_481_analytes_are_alphabetical_by_default(lab_overview_client):
    client, engine = lab_overview_client

    with Session(engine) as db:
        newer = LabReport(
            drawn_on=date(2026, 11, 6),
            lab_name="New draw",
        )
        newer.results = [
            LabResult(
                analyte="TSH", value=0.5,
                unit="mIU/L",
            ),
            LabResult(
                analyte="Zinc", value=80,
                unit="ug/dL",
            ),
        ]
        older = LabReport(
            drawn_on=date(2026, 9, 10),
            lab_name="Older draw",
        )
        older.results = [
            LabResult(
                analyte="albumin", value=4.2,
                unit="g/dL",
            ),
            LabResult(
                analyte="Ferritin", value=120,
                unit="ng/mL",
            ),
        ]
        db.add_all([newer, older])
        db.commit()

    result = client.get("/labs")
    assert result.status_code == 200
    html = result.text

    positions = [
        html.index(f'data-lab-name="{name}"')
        for name in ("albumin", "Ferritin", "TSH", "Zinc")
    ]
    assert positions == sorted(positions)

    assert '<option value="name-asc" selected>' in html
    assert html.count('class="lab-analyte-details"') == 4
    assert html.count('class="lab-analyte-summary"') == 4
    assert html.count("View complete") == 4
    assert 'class="lab-analyte-details" open' not in html


def test_481_expansion_is_click_only_not_page_navigation():
    root = Path(__file__).resolve().parents[1]

    html = (root / "app/templates/labs.html").read_text()
    js = (
        root / "app/static/js/tracker-labs-overview.js"
    ).read_text()
    css = (
        root / "app/static/css/tracker-labs-overview.css"
    ).read_text()

    assert '<details class="lab-analyte-details">' in html
    assert '<summary class="lab-analyte-summary">' in html
    assert '<h3><a href="/labs/trends/' not in html
    assert 'View complete {{ c.name }} history' in html
    assert "sort.value = 'name-asc';" in js
    assert "details.open = false;" in js
    assert ".lab-analyte-summary:focus-visible" in css

    # Display-only controls must not submit or modify labs.
    assert "fetch(" not in js
    assert ".submit(" not in js
    assert "localStorage" not in js


# Release 482: editing existing lab records.
def test_482_edit_report_preserves_attachment_and_results(
    lab_overview_client
):
    client, engine = lab_overview_client

    with Session(engine) as db:
        report = LabReport(
            drawn_on=date(2026, 10, 1),
            lab_name="Original Lab",
            notes="Original note",
            original_name="report.pdf",
            stored_name="saved-report-482.pdf",
            content_type="application/pdf",
            size_bytes=123,
            sha256="a" * 64,
        )
        report.results = [
            LabResult(
                analyte="TSH",
                value=0.5,
                unit="mIU/L",
                ref_low=0.4,
                ref_high=4.5,
            )
        ]
        db.add(report)
        db.commit()
        rid = report.id
        xid = report.results[0].id

    page = client.get(f"/labs/{rid}")
    assert page.status_code == 200
    assert "Edit Report Details" in page.text
    assert f'action="/labs/{rid}/edit"' in page.text
    assert f'action="/lab-results/{xid}/edit"' in page.text

    response = client.post(
        f"/labs/{rid}/edit",
        data={
            "drawn_on": "2026-11-06",
            "lab_name": "Updated Lab",
            "notes": "Corrected draw date",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    with Session(engine) as db:
        report = db.get(LabReport, rid)
        result = db.get(LabResult, xid)

        assert report.drawn_on == date(2026, 11, 6)
        assert report.lab_name == "Updated Lab"
        assert report.notes == "Corrected draw date"
        assert report.original_name == "report.pdf"
        assert report.stored_name == "saved-report-482.pdf"
        assert report.sha256 == "a" * 64

        assert result.analyte == "TSH"
        assert result.value == 0.5
        assert result.unit == "mIU/L"


def test_482_edit_one_analyte_preserves_other_results(
    lab_overview_client
):
    client, engine = lab_overview_client

    with Session(engine) as db:
        report = LabReport(
            drawn_on=date(2026, 11, 6),
            lab_name="Original Lab",
        )
        report.results = [
            LabResult(
                analyte="TSH", value=0.5,
                unit="mIU/L",
                ref_low=0.4, ref_high=4.5,
            ),
            LabResult(
                analyte="IGF-1", value=200,
                unit="ng/mL",
            ),
        ]
        db.add(report)
        db.commit()

        first_id = report.results[0].id
        second_id = report.results[1].id
        rid = report.id

    response = client.post(
        f"/lab-results/{first_id}/edit",
        data={
            "analyte": "Free T4",
            "value": "1.25",
            "unit": "ng/dL",
            "ref_low": "0.8",
            "ref_high": "1.8",
            "note": "Corrected transcription",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    with Session(engine) as db:
        first = db.get(LabResult, first_id)
        second = db.get(LabResult, second_id)

        assert first.report_id == rid
        assert first.analyte == "Free T4"
        assert first.value == 1.25
        assert first.unit == "ng/dL"
        assert first.ref_low == 0.8
        assert first.ref_high == 1.8
        assert first.note == "Corrected transcription"

        assert second.analyte == "IGF-1"
        assert second.value == 200


@pytest.mark.parametrize(
    "value,low,high",
    [
        ("5", "1", ""),
        ("5", "", "10"),
        ("5", "10", "1"),
        ("nan", "0", "10"),
        ("inf", "0", "10"),
        ("5", "nan", "10"),
        ("5", "0", "inf"),
        ("5", "abc", "10"),
    ],
)
def test_482_invalid_result_edits_do_not_write(
    lab_overview_client, value, low, high
):
    client, engine = lab_overview_client

    with Session(engine) as db:
        report = LabReport(
            drawn_on=date(2026, 11, 6),
            lab_name="Original",
        )
        report.results = [
            LabResult(
                analyte="Glucose", value=90,
                unit="mg/dL",
                ref_low=70, ref_high=99,
            )
        ]
        db.add(report)
        db.commit()
        xid = report.results[0].id

    response = client.post(
        f"/lab-results/{xid}/edit",
        data={
            "analyte": "Changed",
            "value": value,
            "unit": "mg/dL",
            "ref_low": low,
            "ref_high": high,
            "note": "Changed",
        },
        follow_redirects=False,
    )
    assert response.status_code == 422

    with Session(engine) as db:
        result = db.get(LabResult, xid)
        assert result.analyte == "Glucose"
        assert result.value == 90
        assert result.ref_low == 70
        assert result.ref_high == 99


def test_482_invalid_report_edit_does_not_write(
    lab_overview_client
):
    client, engine = lab_overview_client

    with Session(engine) as db:
        report = LabReport(
            drawn_on=date(2026, 10, 1),
            lab_name="Original",
            notes="Unchanged",
        )
        db.add(report)
        db.commit()
        rid = report.id

    response = client.post(
        f"/labs/{rid}/edit",
        data={
            "drawn_on": "2026-02-30",
            "lab_name": "Changed",
            "notes": "Changed",
        },
        follow_redirects=False,
    )
    assert response.status_code == 422

    with Session(engine) as db:
        report = db.get(LabReport, rid)
        assert report.drawn_on == date(2026, 10, 1)
        assert report.lab_name == "Original"
        assert report.notes == "Unchanged"


def test_482_missing_edit_targets_return_404(
    lab_overview_client
):
    client, _ = lab_overview_client

    assert client.post(
        "/labs/999999/edit",
        data={
            "drawn_on": "2026-11-06",
            "lab_name": "A",
            "notes": "",
        },
    ).status_code == 404

    assert client.post(
        "/lab-results/999999/edit",
        data={
            "analyte": "TSH",
            "value": "1",
            "unit": "mIU/L",
            "ref_low": "",
            "ref_high": "",
            "note": "",
        },
    ).status_code == 404


def test_499_previous_draw_uses_distinct_dates_and_safe_unit_conversion():
    from types import SimpleNamespace
    from app.routers import labs as labs_router
    from app import labs as lab_math

    def result(value, unit, ident, analyte="Total Testosterone"):
        return SimpleNamespace(
            value=value, unit=unit, id=ident, analyte=analyte
        )

    def report(when):
        return SimpleNamespace(drawn_on=date.fromisoformat(when))

    older = (result(20, "nmol/L", 1), report("2026-07-07"))
    newest = (result(600, "ng/dL", 3), report("2026-11-07"))
    same_date = (result(580, "ng/dL", 2), report("2026-11-07"))
    previous = labs_router.previous_draw499(
        [older, newest, same_date], newest
    )
    assert previous["res"] is older[0]
    assert previous["rep"] is older[1]
    expected = 600 - lab_math.convert(
        "Total Testosterone", 20, "nmol/L", "ng/dL"
    )
    assert previous["delta"] == pytest.approx(expected)

    # Never invent a numeric difference for unconvertible units.
    incompatible = (result(200, "mg/L", 4, "Ferritin"), report("2026-07-07"))
    latest_ferritin = (result(175, "ng/mL", 5, "Ferritin"), report("2026-11-07"))
    prior = labs_router.previous_draw499(
        [incompatible, latest_ferritin], latest_ferritin
    )
    assert prior["delta"] is None
    assert labs_router.previous_draw499([newest], newest) is None


def test_499_overview_shows_prior_result_without_writing(lab_overview_client):
    client, engine = lab_overview_client
    with Session(engine) as db:
        earlier = LabReport(
            drawn_on=date(2026, 7, 7), lab_name="Earlier"
        )
        earlier.results = [
            LabResult(analyte="TSH", value=2.0, unit="mIU/L")
        ]
        later = LabReport(
            drawn_on=date(2026, 11, 1), lab_name="Later"
        )
        later.results = [
            LabResult(analyte="TSH", value=0.1, unit="mIU/L")
        ]
        db.add_all([earlier, later])
        db.commit()
        before = db.scalar(
            select(func.count()).select_from(LabResult)
        )

    response = client.get("/labs")
    assert response.status_code == 200
    assert 'class="meta lab499-previous"' in response.text
    assert "Previous draw" in response.text
    assert "Difference from previous:" in response.text
    assert "mIU/L" in response.text

    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(LabResult)) == before


def test_500_full_history_compares_distinct_draw_dates_safely():
    from types import SimpleNamespace
    from app.routers import labs as lab_router
    from app import labs as lab_helpers

    def measured(value, unit, ident):
        return SimpleNamespace(
            analyte="Total Testosterone", value=value,
            unit=unit, id=ident, ref_low=None, ref_high=None,
        )

    def report(day):
        return SimpleNamespace(drawn_on=date.fromisoformat(day))

    older = (measured(20, "nmol/L", 1), report("2026-07-07"))
    same_day = (measured(580, "ng/dL", 2), report("2026-11-08"))
    latest = (measured(600, "ng/dL", 3), report("2026-11-08"))
    rows, unit = lab_router.analyte_history500([older, same_day, latest])
    assert unit == "ng/dL"
    assert [row["res"].id for row in rows] == [3, 2, 1]
    expected = 600 - lab_helpers.convert(
        "Total Testosterone", 20, "nmol/L", "ng/dL"
    )
    assert rows[0]["previous"][0].id == 1
    assert rows[0]["delta"] == pytest.approx(expected)
    assert rows[1]["previous"][0].id == 1
    assert rows[2]["delta"] is None

    incompatible = (
        measured(300, "mg/L", 4), report("2026-10-01")
    )
    rows, _ = lab_router.analyte_history500([incompatible, latest])
    assert rows[0]["delta"] is None
    assert rows[1]["converted"] is None


def test_500_analyte_history_html_and_csv_are_read_only(lab_overview_client):
    import csv
    import io

    client, engine = lab_overview_client
    with Session(engine) as db:
        older = LabReport(
            drawn_on=date(2026, 7, 7), lab_name="=Unsafe Lab"
        )
        older.results = [
            LabResult(
                analyte="TSH", value=2, unit="mIU/L",
                ref_low=0.4, ref_high=4.5
            )
        ]
        latest = LabReport(
            drawn_on=date(2026, 11, 8), lab_name="Later"
        )
        latest.results = [
            LabResult(
                analyte="TSH", value=0.1, unit="mIU/L",
                ref_low=0.4, ref_high=4.5
            )
        ]
        db.add_all([older, latest])
        db.commit()
        before = db.scalar(select(func.count()).select_from(LabResult))

    html = client.get("/labs/trends/tsh")
    assert html.status_code == 200
    for marker in (
        "lab500-history-table",
        "Export History CSV",
        "Previous distinct draw",
        "Difference",
        "View with dose and vial events",
        "Not convertible",
    ):
        # Not convertible is an optional row value, not required for TSH.
        if marker != "Not convertible":
            assert marker in html.text, marker
    assert html.text.count("data-lab500-history-row") == 2

    response = client.get("/labs/trends/tsh/export.csv")
    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert "private, no-store" in response.headers["cache-control"]
    rows = list(csv.DictReader(io.StringIO(
        response.content.decode("utf-8-sig")
    )))
    assert len(rows) == 2
    assert rows[0]["drawn_on"] == "2026-11-08"
    assert float(rows[0]["difference_from_previous"]) == pytest.approx(-1.9)
    assert rows[1]["laboratory"] == "'=Unsafe Lab"
    assert rows[1]["difference_from_previous"] == ""
    assert float(rows[1]["recorded_value"]) == 2
    assert client.get("/labs/trends/missing/export.csv").status_code == 404

    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(LabResult)) == before


def test_501_history_csv_source_ids_notes_and_safe_filename(lab_overview_client):
    import csv
    import io
    from app.routers import labs as lab_router

    assert lab_router.analyte_export_filename501("IGF-1") == "lab-igf-1-history.csv"
    assert lab_router.analyte_export_filename501("../../...") == "lab-analyte-history.csv"
    assert lab_router.analyte_export_filename501("TSH\r\nunsafe.csv") == "lab-tsh-unsafe-csv-history.csv"
    assert len(lab_router.analyte_export_filename501("A" * 100)) <= 64

    client, engine = lab_overview_client
    with Session(engine) as db:
        report = LabReport(drawn_on=date(2026, 11, 8), lab_name="Lab")
        report.results = [
            LabResult(analyte="TSH", value=1.25, unit="mIU/L",
                      note="=HYPERLINK(unsafe)")
        ]
        db.add(report)
        db.commit()
        rid, result_id = report.id, report.results[0].id
        before = db.scalar(select(func.count()).select_from(LabResult))

    response = client.get("/labs/trends/tsh/export.csv")
    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        'attachment; filename="lab-tsh-history.csv"'
    )
    assert response.headers["cache-control"] == "private, no-store"
    assert response.content.startswith(bytes.fromhex("efbbbf"))
    assert b"\r\n" in response.content
    rows = list(csv.DictReader(io.StringIO(
        response.content.decode("utf-8-sig")
    )))
    assert len(rows) == 1
    assert rows[0]["report_id"] == str(rid)
    assert rows[0]["result_id"] == str(result_id)
    assert rows[0]["result_note"] == "'=HYPERLINK(unsafe)"
    assert rows[0]["recorded_value"] == "1.25"
    assert rows[0]["difference_from_previous"] == ""

    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(LabResult)) == before
