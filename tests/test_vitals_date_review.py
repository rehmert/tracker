"""Vitals date filtering and comparison markup remains read-only.

Browser behavior is separately exercised with Playwright; these checks run in
Tracker's normal deployment test gate without a browser dependency.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[1]


def test_vitals_date_filter_controls_render():
    with TestClient(app) as client:
        response = client.get("/vitals?days=30&events=0")
    assert response.status_code == 200
    for marker in (
        'data-vitals-from',
        'data-vitals-through',
        'data-vitals-date-error',
        'data-vitals-weight-compare',
        'data-vitals-bp-compare',
        'data-vitals-pulse-compare',
        'data-vitals-table',
        'data-vitals-export',
        'id="vitals-table-filter-help"',
        'tracker-vitals-tools.css?v=20261103-dates',
        'tracker-vitals-tools.js?v=20261103-dates',
        "They do not change the charts or rolling 7-/30-day summaries.",
    ):
        assert marker in response.text, marker


def test_vitals_date_tools_are_browser_only_and_read_only():
    script = (ROOT / "app/static/js/tracker-vitals-tools.js").read_text()
    assert "function matchesDates(row)" in script
    assert "function describeMatchingReadings()" in script
    assert "row.dataset.vitalsWhen" in script
    assert "from.value > through.value" in script
    assert "matchesDates(row)" in script
    assert "describeMatchingReadings();" in script
    assert "visibleRows().sort" in script
    assert "through?.addEventListener('change', update)" in script
    assert "if (from) from.value = ''" in script
    assert "if (through) through.value = ''" in script
    assert "exportButton.disabled = visible === 0" in script
    assert "fetch(" not in script
    assert "form.submit" not in script
