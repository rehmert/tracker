"""Release 715: no reported endotoxin test is distinct from a reported <1 EU/vial.

Tests use only the isolated QA database supplied by the release runner.
"""
from __future__ import annotations

import re
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import Coa, Compound, Vial
from app.routers.coas import _parse_endotoxin645


def _sample_vial():
    with SessionLocal() as db:
        tag = uuid4().hex[:12]
        compound = Compound(name="QA715-Endotoxin-" + tag, primary_unit="mg")
        db.add(compound)
        db.flush()
        vial = Vial(compound_id=compound.id, content_value=10,
                    content_unit="mg", status="sealed")
        db.add(vial)
        db.commit()
        return vial.id


def _stored(lab):
    with SessionLocal() as db:
        coa = db.scalar(select(Coa).where(Coa.lab_name == lab).order_by(Coa.id.desc()))
        assert coa is not None
        return coa.id, coa.endotoxin_result_kind, coa.endotoxin_eu_per_vial


def _selected(html, value):
    return bool(re.search(
        r'<option\s+value="' + re.escape(value) + r'"\s+selected\b', html
    ))


def test_715_parser_requires_explicit_value_for_reported_endotoxin():
    assert _parse_endotoxin645("untested", "") == ("untested", None)
    assert _parse_endotoxin645("lt1", "") == ("lt1", None)
    assert _parse_endotoxin645("exact", "4.308") == ("exact", 4.308)
    with pytest.raises(ValueError, match="Remove the numeric"):
        _parse_endotoxin645("untested", "0")
    with pytest.raises(ValueError, match="Remove the numeric"):
        _parse_endotoxin645("lt1", "0.3")
    for kind in ("", "unknown", "no_data"):
        with pytest.raises(ValueError, match="Select Untested"):
            _parse_endotoxin645(kind, "")
    for number in ("", "-0.3", "nan", "inf", "invalid"):
        with pytest.raises(ValueError):
            _parse_endotoxin645("exact", number)


def test_715_new_form_vial_form_and_legacy_null_default_to_untested():
    with TestClient(app) as client:
        vid = _sample_vial()
        add = client.get("/coas/new")
        vial = client.get(f"/vials/{vid}")
        assert add.status_code == vial.status_code == 200
        assert _selected(add.text, "untested")
        assert _selected(vial.text, "untested")
        assert not _selected(add.text, "lt1")
        assert not _selected(vial.text, "lt1")
        for page in (add.text, vial.text):
            assert 'option value="lt1"' in page
            assert 'option value="exact"' in page
            assert 'option value="untested"' in page

        tag = uuid4().hex
        lab = "QA715-legacy-" + tag
        with SessionLocal() as db:
            record = Coa(lab_name=lab, stored_name="metadata-715-" + tag)
            db.add(record)
            db.commit()
            cid = record.id
        old = client.get(f"/coas/{cid}")
        assert old.status_code == 200
        assert _selected(old.text, "untested")
        assert "No EU/vial result is stored for this older COA" in old.text
        with SessionLocal() as db:
            old_row = db.get(Coa, cid)
            assert old_row.endotoxin_result_kind is None
            assert old_row.endotoxin_eu_per_vial is None


def test_715_create_and_edit_do_not_fabricate_less_than_one_results():
    with TestClient(app) as client:
        vid = _sample_vial()
        a = "QA715-new-" + uuid4().hex
        created = client.post("/coas/new", data={"vial_id": str(vid), "lab_name": a},
                              follow_redirects=False)
        assert created.status_code == 303
        cid, kind, value = _stored(a)
        assert (kind, value) == ("untested", None)
        assert _selected(client.get(f"/coas/{cid}").text, "untested")

        b = "QA715-vial-" + uuid4().hex
        uploaded = client.post(f"/vials/{vid}/coas", data={"lab_name": b},
                               follow_redirects=False)
        assert uploaded.status_code == 303
        _, kind, value = _stored(b)
        assert (kind, value) == ("untested", None)

        # Historical choices survive GET and normal edit form selection.
        as_lt1 = client.post(f"/coas/{cid}/edit", data={
            "lab_name": a, "endotoxin_result_kind": "lt1",
        }, follow_redirects=False)
        assert as_lt1.status_code == 303
        assert _stored(a)[1:] == ("lt1", None)
        assert _selected(client.get(f"/coas/{cid}").text, "lt1")

        as_exact = client.post(f"/coas/{cid}/edit", data={
            "lab_name": a, "endotoxin_result_kind": "exact",
            "endotoxin_eu_per_vial": "4.308",
        }, follow_redirects=False)
        assert as_exact.status_code == 303
        assert _stored(a)[1:] == ("exact", 4.308)
        assert _selected(client.get(f"/coas/{cid}").text, "exact")

        # Refuse contradictory "Untested" with a numerical result: preserve the
        # previous exact record instead of silently clearing a measurement.
        rejected = client.post(f"/coas/{cid}/edit", data={
            "lab_name": a, "endotoxin_result_kind": "untested",
            "endotoxin_eu_per_vial": "4.308",
        }, follow_redirects=False)
        assert rejected.status_code == 303
        assert "err=" in rejected.headers.get("location", "")
        assert _stored(a)[1:] == ("exact", 4.308)

        reset = client.post(f"/coas/{cid}/edit", data={
            "lab_name": a, "endotoxin_result_kind": "untested",
        }, follow_redirects=False)
        assert reset.status_code == 303
        assert _stored(a)[1:] == ("untested", None)
        assert _selected(client.get(f"/coas/{cid}").text, "untested")

        # Legacy signed/parameter-omitted entry paths default safely.
        omitted = client.post(f"/coas/{cid}/edit", data={"lab_name": a},
                              follow_redirects=False)
        assert omitted.status_code == 303
        assert _stored(a)[1:] == ("untested", None)
