"""Release 614–616 bundled, read-only workflow improvements.

The existing isolated test database supplies QA-only data; no production
inventory is altered by the timeline, calendar, or health review pages.
"""
from datetime import date
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from jinja2 import Environment

from app.main import app
from tests.test_release611_blend_calendar import _seed

ROOT = Path(__file__).resolve().parents[1]


def test_616_bundle_templates_parse_and_preserve_origins():
    for filename in ("doses.html", "calendar.html", "inventory_health.html"):
        Environment().parse(
            (ROOT / "app/templates" / filename).read_text(encoding="utf-8")
        )
    doses = (ROOT / "app/templates/doses.html").read_text()
    assert 'id="dose-history-unified614"' in doses
    assert 'id="dose-body"' in doses  # original HTMX mutation target
    assert 'id="blend-dose-history611"' in doses
    assert 'action="/doses"' in doses
    assert 'name="history_date"' in doses
    assert 'name="history_source"' in doses
    assert 'name="history_kind"' in doses
    assert 'href="/blends/{{ r.blend.id }}"' in doses
    calendar = (ROOT / "app/templates/calendar.html").read_text()
    assert "history_date={{ d.date.isoformat() }}" in calendar
    assert calendar.count("Review recorded history") == 2
    assert 'href="/blends/{{ x.actual_blend_id }}"' in calendar
    assert 'href="/blends/{{ x.blend_id }}"' in calendar


def test_616_combined_history_shows_blends_once_and_filters():
    blend_id, compound_ids, today, label = _seed()
    stamp = today.isoformat()
    with TestClient(app) as client:
        created = client.post(
            f"/blends/{blend_id}/doses",
            data={
                "taken_at": stamp + "T10:30",
                "volume_ml": "0.2",
                "kind": "dose",
                "submission_token": str(uuid4()),
            },
            follow_redirects=False,
        )
        assert created.status_code == 303

        combined = client.get(
            f"/doses?compound_id={compound_ids[0]}&history_date={stamp}"
            "&history_source=blend&history_kind=dose"
        )
        assert combined.status_code == 200
        assert combined.text.count('data-timeline-source="blend"') == 1
        assert 'data-timeline-source="vial"' not in combined.text
        assert f'href="/blends/{blend_id}"' in combined.text
        assert label in combined.text
        assert 'id="dose-body"' in combined.text

        empty = client.get(
            f"/doses?compound_id={compound_ids[0]}&history_date={stamp}"
            "&history_source=blend&history_kind=waste"
        )
        assert empty.status_code == 200
        assert "No recent entries match these filters." in empty.text
        assert 'data-timeline-source="blend"' not in empty.text

        calendar = client.get(f"/calendar?month={stamp[:7]}")
        assert calendar.status_code == 200
        assert f"history_date={stamp}#dose-history-unified614" in calendar.text
        assert f'href="/blends/{blend_id}"' in calendar.text


def test_616_inventory_health_review_is_read_only_and_filterable():
    with TestClient(app) as client:
        for severity in ("all", "error", "warning"):
            response = client.get("/inventory-health", params={"severity": severity})
            assert response.status_code == 200
            assert 'id="inventory-health-findings616"' in response.text
            assert f'<option value="{severity}" selected>' in response.text
            assert 'href="/audit-history"' in response.text
            assert 'href="/reconciliation"' in response.text
            assert "Severity filtering does not change stock" in response.text
        invalid = client.get("/inventory-health?severity=not-valid")
        assert invalid.status_code == 200
        assert '<option value="all" selected>' in invalid.text
