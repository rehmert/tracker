"""Bulk vial preview export is explicitly read-only and is discoverable.

The deployment gate runs this static contract test even when Chromium is
unavailable; browser behavior is covered separately in the Playwright suite.
"""
from pathlib import Path

from fastapi.testclient import TestClient
from app.main import app


ROOT = Path(__file__).resolve().parents[1]


def test_preview_export_is_present_and_clearly_unapplied():
    with TestClient(app) as client:
        response = client.get("/vials")
    assert response.status_code == 200
    markup = response.text
    assert 'id="bulk-server-review"' in markup
    assert 'id="bulk-review-export" disabled' in markup
    assert "Export proposed changes CSV" in markup
    assert "not a record of changes applied to inventory" in markup
    assert 'id="bulk-server-review-confirm"' in markup


def test_preview_export_uses_full_validated_change_set():
    markup = (ROOT / "app/templates/vials.html").read_text()
    segment = markup.split("function exportProposedChanges()", 1)[1].split(
        'exportButton?.addEventListener("click", exportProposedChanges)', 1
    )[0]

    assert 'reviewData.rows.filter(entry => entry.changed)' in segment
    assert 'entry.current' in segment and 'entry.proposed' in segment
    assert 'PROPOSED - NOT SAVED' in segment
    assert 'tracker-bulk-vial-proposed-changes.csv' in segment
    assert 'URL.createObjectURL(blob)' in segment
    assert 'safe.replaceAll(' in segment
    assert 'form.submit(' not in segment
    assert 'fetch(' not in segment
