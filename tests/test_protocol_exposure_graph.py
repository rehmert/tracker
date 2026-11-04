"""Batch 52: protocol detail exposure remains read-only."""
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models import Compound, Protocol
from app.routers import pk as router

ROOT = Path(__file__).resolve().parents[1]


def item(unit="mg"):
    return SimpleNamespace(
        compound_id=1,
        amount_value=5,
        amount_unit=unit,
        freq_count=1,
        freq_period="week",
        start_week=1,
        end_week=None,
        dose_days="",
        dose_time="09:00",
    )


class FakeDB:
    def __init__(self, protocol):
        self.protocol = protocol

    def get(self, model, identity):
        if model is Protocol:
            return self.protocol
        if model is Compound and identity == 1:
            return SimpleNamespace(name="Tirzepatide")
        return None


@pytest.mark.parametrize("active", [True, False])
def test_active_and_what_if_protocols_can_graph(
    monkeypatch, active
):
    p = SimpleNamespace(
        name="Test protocol",
        is_active=active,
        start_date=date(2026, 11, 1),
        end_date=None,
        horizon_weeks=2,
        items=[item()],
    )
    calls = []

    def fake_series(start, end, actual, planned, *params,
                    step_hours=12):
        calls.append((actual, planned))
        return [
            {"at": start.isoformat(), "planned": 0.0},
            {"at": end.isoformat(), "planned": 3.0},
        ]

    monkeypatch.setattr(router.pk, "series", fake_series)

    response = router.saved_protocol_exposure(
        1, db=FakeDB(p)
    )
    data = json.loads(response.body)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert data["status"] == (
        "Active" if active else "What-if"
    )
    assert len(data["graphs"]) == 1
    assert data["graphs"][0]["dose_count"] == 2
    assert calls[0][0] == []
    assert len(calls[0][1]) == 2


def test_undated_what_if_uses_illustrative_start(
    monkeypatch,
):
    p = SimpleNamespace(
        name="Undated plan",
        is_active=False,
        start_date=None,
        end_date=None,
        horizon_weeks=1,
        items=[item()],
    )
    monkeypatch.setattr(
        router.pk, "series",
        lambda start, end, actual, planned,
        *args, **kwargs: [
            {"at": start.isoformat(), "planned": 0},
            {"at": end.isoformat(), "planned": 2},
        ],
    )

    data = json.loads(
        router.saved_protocol_exposure(
            1, db=FakeDB(p)
        ).body
    )
    assert data["assumed_start"] is True
    assert data["start_date"] == date.today().isoformat()
    assert data["graphs"]


def test_nonmass_units_are_not_guessed():
    p = SimpleNamespace(
        name="IU-only plan",
        is_active=False,
        start_date=date(2026, 11, 1),
        end_date=None,
        horizon_weeks=2,
        items=[item("IU")],
    )
    data = json.loads(
        router.saved_protocol_exposure(
            1, db=FakeDB(p)
        ).body
    )
    assert not data["graphs"]
    assert any(
        "non-mass" in entry["reason"]
        for entry in data["skipped"]
    )


def test_protocol_detail_exposes_read_only_button():
    html = (
        ROOT / "app/templates/protocol_edit.html"
    ).read_text()
    js = (
        ROOT / "app/static/js/"
        "tracker-protocol-exposure.js"
    ).read_text()

    assert 'id="protocolExposureButton"' in html
    assert 'id="protocolExposureResults"' in html
    assert "tracker-protocol-exposure.js?v=batch52" in html
    assert "tracker-pk-axes.js?v=batch50" in html
    assert 'window.trackerPkAxes.draw({' in js
    assert 'method:"POST"' not in js
    assert "/pk/protocol-exposure/" in js
