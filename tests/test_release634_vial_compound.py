"""Release 634 — isolated compound-correction integration tests.

Only a temporary SQLite database is used. No live inventory is modified.
"""
import json
from datetime import datetime
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models import Compound, Vial, DoseLog, Coa, ChangeAudit
from app.routers import vials
from app.routers.vials import _bulk_parse
from starlette.datastructures import FormData


@pytest.fixture
def env(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'reassign.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    @event.listens_for(engine, "connect")
    def fk(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session.begin() as db:
        source = Compound(name="Correction source", primary_unit="mg")
        target = Compound(name="Correction target", primary_unit="mg")
        iu = Compound(name="Correction IU", primary_unit="IU")
        db.add_all([source, target, iu])
        db.flush()
        db.add_all([
            Vial(compound_id=source.id, content_value=10,
                 content_unit="mg", status="sealed", label="First"),
            Vial(compound_id=source.id, content_value=10,
                 content_unit="mg", status="sealed", label="Second"),
        ])
    app = FastAPI()
    app.include_router(vials.router)

    def isolated_db():
        with Session() as db:
            yield db
    app.dependency_overrides[get_db] = isolated_db
    with TestClient(app, follow_redirects=False) as client:
        yield {"db": Session, "client": client, "source": 1, "target": 2, "iu": 3}
    engine.dispose()


def post(client, route, data):
    return client.post(
        route,
        content=urlencode(data),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def correction(ids, target):
    return [("vial_ids", str(i)) for i in ids] + [
        ("mode_compound_id", "set"),
        ("value_compound_id", str(target)),
    ]


def test_parse_requires_compound_id_and_never_clears():
    ids, changes = _bulk_parse(FormData(correction([2, 1], 3)))
    assert ids == [1, 2]
    assert changes == {"compound_id": 3}
    for mode, value in (("clear", ""), ("set", ""), ("set", "nope"),
                        ("set", "-1"), ("set", "0")):
        with pytest.raises(ValueError):
            _bulk_parse(FormData([
                ("vial_ids", "1"), ("mode_compound_id", mode),
                ("value_compound_id", value),
            ]))


def test_bulk_preview_and_confirm_are_audited_and_atomic(env):
    data = correction([1, 2], env["target"])
    preview = post(env["client"], "/vials/bulk/preview", data)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["ok"] is True
    assert body["count"] == 2
    assert {r["current"] for r in body["rows"]} == {"Correction source"}
    assert {r["proposed"] for r in body["rows"]} == {"Correction target"}
    with env["db"]() as db:
        assert all(db.get(Vial, i).compound_id == env["source"] for i in (1, 2))
    result = post(env["client"], "/vials/bulk", data + [
        ("bulk_preview_snapshot", body["snapshot"]),
    ])
    assert result.status_code == 303
    assert "err=" not in result.headers["location"]
    with env["db"]() as db:
        assert all(db.get(Vial, i).compound_id == env["target"] for i in (1, 2))
        audits = list(db.scalars(select(ChangeAudit).where(
            ChangeAudit.entity_type == "vial",
            ChangeAudit.action == "bulk_update",
        )))
        assert len(audits) == 2
        for audit in audits:
            assert json.loads(audit.before_json) == {"compound_id": env["source"]}
            assert json.loads(audit.after_json) == {"compound_id": env["target"]}


def test_bulk_rejects_nonexistent_and_iu_without_partial_writes(env):
    for target in (99999, env["iu"]):
        result = post(env["client"], "/vials/bulk", correction([1, 2], target))
        assert result.status_code == 303
        assert "err=" in result.headers["location"]
        with env["db"]() as db:
            assert all(db.get(Vial, i).compound_id == env["source"] for i in (1, 2))


def test_bulk_rejects_history_on_one_vial_and_keeps_both(env):
    with env["db"].begin() as db:
        db.get(Vial, 2).coa = Coa()
    result = post(env["client"], "/vials/bulk",
                  correction([1, 2], env["target"]))
    assert result.status_code == 303
    assert "err=" in result.headers["location"]
    with env["db"]() as db:
        assert all(db.get(Vial, i).compound_id == env["source"] for i in (1, 2))
        assert list(db.scalars(select(ChangeAudit))) == []


def test_single_vial_change_preserves_content_and_writes_audit(env):
    form = [
        ("compound_id", str(env["target"])),
        ("label", "First"), ("lot", ""), ("status", "sealed"),
        ("content_value", "10"), ("content_unit", "mg"),
    ]
    response = post(env["client"], "/vials/1", form)
    assert response.status_code == 303
    assert "err=" not in response.headers["location"]
    with env["db"]() as db:
        vial = db.get(Vial, 1)
        assert vial.compound_id == env["target"]
        assert vial.content_value == 10 and vial.content_unit == "mg"
        audit = db.scalar(select(ChangeAudit).where(
            ChangeAudit.entity_id == 1,
            ChangeAudit.action == "compound_reassign",
        ))
        assert audit is not None
        assert json.loads(audit.before_json)["compound_id"] == env["source"]
        assert json.loads(audit.after_json)["compound_id"] == env["target"]


def test_single_vial_bad_target_is_denied_without_mutation(env):
    response = post(env["client"], "/vials/1", [
        ("compound_id", str(env["iu"])), ("status", "sealed"),
        ("content_value", "10"), ("content_unit", "mg"),
    ])
    assert response.status_code == 303
    assert "err=" in response.headers["location"]
    with env["db"]() as db:
        assert db.get(Vial, 1).compound_id == env["source"]


def test_templates_expose_single_and_bulk_reassignment():
    from pathlib import Path
    from jinja2 import Environment
    root = Path(__file__).resolve().parents[1]
    one = (root / "app/templates/vial_detail.html").read_text()
    many = (root / "app/templates/vials.html").read_text()
    Environment().parse(one)
    Environment().parse(many)
    assert '<select name="compound_id" required>' in one
    assert "('compound_id','Compound','compound')" in many
    assert 'data-bulk-focus-field="compound_id"' in many
    assert 'name="value_{{ key }}"' in many
    assert "Choose destination compound" in many


def test_logged_dose_blocks_compound_reassignment_for_entire_batch(env):
    with env["db"].begin() as db:
        db.add(DoseLog(
            vial_id=2, taken_at=datetime(2026, 11, 15, 10, 0),
            entered_value=1, entered_unit="mg", amount_base=1000,
        ))
    result = post(env["client"], "/vials/bulk",
                  correction([1, 2], env["target"]))
    assert result.status_code == 303
    assert "err=" in result.headers["location"]
    with env["db"]() as db:
        assert all(db.get(Vial, i).compound_id == env["source"] for i in (1, 2))


def test_stale_bulk_preview_cannot_commit_compound_change(env):
    data = correction([1, 2], env["target"])
    response = post(env["client"], "/vials/bulk/preview", data)
    assert response.status_code == 200
    snapshot = response.json()["snapshot"]
    with env["db"].begin() as db:
        db.get(Vial, 2).lot = "Changed after preview"
    result = post(env["client"], "/vials/bulk", data + [
        ("bulk_preview_snapshot", snapshot),
    ])
    assert result.status_code == 303
    assert "err=" in result.headers["location"]
    with env["db"]() as db:
        assert all(db.get(Vial, i).compound_id == env["source"] for i in (1, 2))


def test_existing_bulk_lot_edit_is_not_blocked_by_unused_compound_selector(env):
    data = [("vial_ids", "1"), ("mode_lot", "set"),
            ("value_lot", "Correction batch")]
    response = post(env["client"], "/vials/bulk", data)
    assert response.status_code == 303
    assert "err=" not in response.headers["location"]
    with env["db"]() as db:
        assert db.get(Vial, 1).lot == "Correction batch"
        assert db.get(Vial, 1).compound_id == env["source"]
