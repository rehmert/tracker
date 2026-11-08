"""Release 515: protocol form integrity, secondary weekly completeness and COA ORM.

Uses the existing pytest isolated database; no DEV/PROD data is accessed.
"""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app import calc
from app.db import SessionLocal
from app.main import app
from app.models import Coa, Compound, Protocol, ProtocolItem, Vial
from app.routers import protocols
from app import secondary_preview430 as secondary


def _refs():
    return {7: SimpleNamespace(name="Test compound", dim=None, conc_per_ml=None)}


@pytest.mark.parametrize(("amount", "frequency", "period", "unit"), [
    ("nan", "1", "week", "mg"),
    ("inf", "1", "week", "mg"),
    ("-Infinity", "1", "week", "mg"),
    ("-1", "1", "week", "mg"),
    ("1e309", "1", "week", "mg"),
    ("1", "nan", "week", "mg"),
    ("1", "-1", "week", "mg"),
    ("1", "Infinity", "interval", "mg"),
    ("1", "0", "interval", "mg"),
    ("1", "1", "nonsense", "mg"),
    ("1", "1", "week", "bogus"),
])
def test_515_rejects_invalid_protocol_numeric_rows(amount, frequency, period, unit):
    results = protocols._parse_rows(
        _refs(), ["7"], [amount], [unit], [frequency], [period]
    )
    assert len(results) == 1
    assert isinstance(results[0], calc.ItemResult)
    assert results[0].warnings
    assert not results[0].ok


@pytest.mark.parametrize("field", range(5))
def test_515_rejects_truncated_protocol_field_arrays(field):
    fields = [["7", "7"], ["1", "2"], ["mg", "mg"], ["1", "1"],
              ["week", "week"]]
    fields[field].pop()
    with pytest.raises(HTTPException) as raised:
        protocols._parse_rows(_refs(), *fields)
    assert raised.value.status_code == 400
    assert "Incomplete" in raised.value.detail


@pytest.mark.parametrize(("raw", "expected"), [
    ("nan", 12.0), ("Infinity", 12.0), ("-inf", 12.0),
    ("16", 16.0), ("9999", 520.0),
])
def test_515_horizon_never_returns_nonfinite(raw, expected):
    assert protocols._horizon(raw) == expected


def test_515_valid_protocol_amounts_still_parse():
    result = protocols._parse_rows(
        _refs(), ["7", "7"], ["1.25", "0"], ["mg", "IU"],
        ["1", "0"], ["week", "day"]
    )
    assert len(result) == 2
    assert all(isinstance(item, calc.ItemInput) for item in result)


def test_515_invalid_protocol_form_does_not_mutate_existing_plan():
    with TestClient(app, follow_redirects=False) as client:
        with SessionLocal() as db:
            compound = Compound(name="515 test compound", category="peptide")
            protocol = Protocol(name="515 preserved plan", horizon_weeks=12)
            protocol.items.append(
                ProtocolItem(compound=compound, position=0,
                             amount_value=1.0, amount_unit="mg",
                             freq_count=1.0, freq_period="week",
                             start_week=1)
            )
            db.add(protocol)
            db.commit()
            pid, cid = protocol.id, compound.id

        payload = {
            "name": "Changed title must not persist",
            "horizon_weeks": "nan",
            "compound_id": [str(cid)],
            "amount": ["NaN"],
            "unit": ["mg"],
            "freq_count": ["1"],
            "freq_period": ["week"],
        }
        rejected = client.post(f"/protocols/{pid}/save", data=payload)
        assert rejected.status_code == 200
        with SessionLocal() as db:
            restored = db.get(Protocol, pid)
            assert restored.name == "515 preserved plan"
            assert restored.horizon_weeks == 12
            assert len(restored.items) == 1
            assert restored.items[0].amount_value == 1

        rejected = client.post(f"/protocols/{pid}/save", data={
            **payload,
            "amount": [],
            "horizon_weeks": "12",
        })
        assert rejected.status_code == 400
        with SessionLocal() as db:
            restored = db.get(Protocol, pid)
            assert restored.name == "515 preserved plan"
            assert len(restored.items) == 1


@pytest.mark.parametrize("reports", [
    [],
    [{"user_id": 2, "day": "2026-11-08"}],
    [None] * 7,
])
def test_515_secondary_week_rejects_incomplete_worker_results(
    monkeypatch, reports
):
    from starlette.requests import Request

    monkeypatch.setattr(secondary, "require_preview", lambda: None)
    monkeypatch.setattr(secondary, "_session_user", lambda token: 2)
    monkeypatch.setattr(
        secondary, "private_food_week_orm470",
        lambda request, day: reports,
    )
    request = Request({
        "type": "http", "method": "GET",
        "path": "/secondary/food/week",
        "query_string": b"day=2026-11-08",
        "headers": [],
    })
    with pytest.raises(HTTPException) as raised:
        secondary.secondary_food_week453(request)
    assert raised.value.status_code == 503


def test_515_secondary_week_accepts_only_exact_seven_scoped_days(monkeypatch):
    from starlette.requests import Request
    last = date(2026, 11, 8)
    reports = [
        {"user_id": 2, "day": (last - timedelta(days=6-i)).isoformat()}
        for i in range(7)
    ]
    monkeypatch.setattr(secondary, "require_preview", lambda: None)
    monkeypatch.setattr(secondary, "_session_user", lambda token: 2)
    monkeypatch.setattr(
        secondary, "private_food_week_orm470",
        lambda request, day: reports,
    )
    monkeypatch.setattr(secondary, "render_week453", lambda *args: "<p>OK</p>")
    request = Request({
        "type": "http", "method": "GET",
        "path": "/secondary/food/week",
        "query_string": b"day=2026-11-08",
        "headers": [],
    })
    assert secondary.secondary_food_week453(request).status_code == 200


def test_515_coa_relationships_keep_one_mapping_and_deduplicated_views():
    assert "linked_coas" in inspect(Vial).relationships
    assert "linked_vials" in inspect(Coa).relationships
    vial = Vial(id=7)
    coa = Coa(id=3, tested_on=date(2026, 11, 8))
    vial.coa = coa
    vial.linked_coas.append(coa)
    assert [c.id for c in vial.all_coas] == [3]
    assert [v.id for v in coa.all_vials] == [7]
