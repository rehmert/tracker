"""Release 640: keep Release 579 CSRF witnesses and review the two new catalog GETs."""
from pathlib import Path

import pytest

from scripts import tracker_csrf_runtime_report579 as report

ROOT = Path(__file__).resolve().parents[1]


def test_640_only_two_new_read_only_catalog_callsites():
    result = report.reviewed_js_source_callsites(ROOT)
    assert result["tracked_js_callsites"] == 51
    assert result["witnessed_js_callsites"] == 2
    assert result["not_witnessed_in_579"] == 49
    assert result["unqualified_coa_multi651_callsites"] == 1
    assert result["unqualified_workout_offline668_callsites"] == 1
    assert len(result["source_refs"]) == 2


def test_640_new_catalog_calls_are_explicit_gets():
    source = (ROOT / report.REGIMEN_CATALOG_SOURCE).read_text()
    lines = source.splitlines()
    catalog_callsites = [
        i for i, line in enumerate(lines) if "fetch(" in line
    ]
    assert len(catalog_callsites) == 2
    for number, expected in zip(catalog_callsites, report.REGIMEN_CATALOG_GET_PATHS):
        assert expected in lines[number]
        assert "method: 'GET'" in "\n".join(lines[number:number+4])


def test_640_runtime_witnesses_remain_unexpanded():
    assert report.TRACKED_FETCH_SOURCES == {
        "app/static/js/tracker-mobile-quick528.js",
        "app/static/notes_editor.js",
    }
    assert report.REGIMEN_CATALOG_SOURCE not in report.TRACKED_FETCH_SOURCES
