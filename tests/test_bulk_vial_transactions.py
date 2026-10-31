

"""Stage 6: isolated SQLite and HTTP bulk-vial integration tests.

Uses a temporary file-backed database and a minimal FastAPI
application containing Tracker's real vial router.

No production database, authentication, or lifespan migration
is involved.
"""

import json
from datetime import date
from urllib.parse import urlencode

import pytest

pytestmark = pytest.mark.quick

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.inventory_lock import reserve_inventory_write
from app.models import Compound, Vial, ChangeAudit
from app.routers import vials


@pytest.fixture
def environment(tmp_path):
    database = tmp_path / "bulk_transactions.sqlite3"

    engine = create_engine(
        f"sqlite:///{database}",
        connect_args={
            "check_same_thread": False,
            "timeout": 0.15,
        },
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=150")
        cursor.close()

    Base.metadata.create_all(engine)

    Session = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    with Session.begin() as db:
        compound = Compound(
            name="Stage 6 Test Compound",
            category="peptide",
        )
        db.add(compound)
        db.flush()

        for number in range(1, 4):
            db.add(Vial(
                compound_id=compound.id,
                label=f"Test vial {number}",
                lot="ORIGINAL",
                cap_color="Red",
                status="sealed",
                content_value=10.0,
                content_unit="mg",
                received_on=date(2026, 1, 10),
            ))

    # Isolated FastAPI app: actual vial router and dependency,
    # without Tracker's global authentication or production
    # lifespan/database migration.
    app = FastAPI()
    app.include_router(vials.router)

    def test_db():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = test_db

    with TestClient(app, follow_redirects=False) as client:
        yield {
            "engine": engine,
            "Session": Session,
            "client": client,
        }

    engine.dispose()


def payload(ids=(1, 2), field="lot", value="UPDATED"):
    data = [
        ("vial_ids", str(vial_id))
        for vial_id in ids
    ]

    data.extend([
        ("mode_" + field, "set"),
        ("value_" + field, value),
    ])

    return data


def post_form(client, url, data):
    """Submit repeated form keys as standard URL-encoded data."""
    return client.post(
        url,
        content=urlencode(data, doseq=True),
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        },
    )


def preview(env, data):
    response = post_form(
        env["client"],
        "/vials/bulk/preview",
        data,
    )
    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True
    return response.json()


def read_vials(env):
    with env["Session"]() as db:
        return {
            vial.id: vial
            for vial in db.scalars(
                select(Vial).order_by(Vial.id)
            )
        }


def audit_rows(env):
    with env["Session"]() as db:
        return list(db.scalars(
            select(ChangeAudit)
            .where(ChangeAudit.action == "bulk_update")
            .order_by(ChangeAudit.id)
        ))


def test_preview_does_not_modify_inventory(environment):
    env = environment
    data = payload()

    result = preview(env, data)

    assert result["count"] == 2
    assert result["fields"] == 1
    assert len(result["rows"]) == 2
    assert len(result["snapshot"]) == 64

    records = read_vials(env)

    assert records[1].lot == "ORIGINAL"
    assert records[2].lot == "ORIGINAL"
    assert audit_rows(env) == []


def test_successful_bulk_update_is_atomic(environment):
    env = environment
    data = payload()

    result = preview(env, data)

    response = post_form(
        env["client"],
        "/vials/bulk",
        data + [
            ("bulk_preview_snapshot", result["snapshot"])
        ],
    )

    assert response.status_code in (302, 303)

    records = read_vials(env)

    assert records[1].lot == "UPDATED"
    assert records[2].lot == "UPDATED"
    assert records[3].lot == "ORIGINAL"

    audits = audit_rows(env)

    assert len(audits) == 2
    assert {audit.entity_id for audit in audits} == {1, 2}

    for audit in audits:
        assert json.loads(audit.before_json)["lot"] == "ORIGINAL"
        assert json.loads(audit.after_json)["lot"] == "UPDATED"


def test_stale_preview_rejected(environment):
    env = environment
    data = payload()

    result = preview(env, data)

    with env["Session"].begin() as db:
        vial = db.get(Vial, 1)
        vial.cap_color = "Blue"

    response = post_form(
        env["client"],
        "/vials/bulk",
        data + [
            ("bulk_preview_snapshot", result["snapshot"])
        ],
    )

    assert response.status_code in (302, 303)

    records = read_vials(env)

    assert records[1].lot == "ORIGINAL"
    assert records[2].lot == "ORIGINAL"
    assert records[1].cap_color == "Blue"
    assert audit_rows(env) == []


def test_invalid_date_rolls_back_all_vials(environment):
    env = environment

    data = payload(
        field="first_punctured_on",
        value="2026-01-01",
    )

    response = post_form(
        env["client"],
        "/vials/bulk",
        data,
    )

    assert response.status_code in (302, 303)

    records = read_vials(env)

    assert records[1].first_punctured_on is None
    assert records[2].first_punctured_on is None
    assert audit_rows(env) == []


def test_missing_vial_rejects_entire_batch(environment):
    env = environment

    response = post_form(
        env["client"],
        "/vials/bulk",
        payload(ids=(1, 999999)),
    )

    assert response.status_code in (302, 303)

    records = read_vials(env)

    assert records[1].lot == "ORIGINAL"
    assert audit_rows(env) == []


def test_repeated_identical_update_no_duplicate_audit(environment):
    env = environment
    data = payload()

    first = post_form(
        env["client"],
        "/vials/bulk",
        data,
    )
    assert first.status_code in (302, 303)

    assert len(audit_rows(env)) == 2

    second = post_form(
        env["client"],
        "/vials/bulk",
        data,
    )
    assert second.status_code in (302, 303)

    assert len(audit_rows(env)) == 2


def test_write_reservation_blocks_second_writer(environment):
    env = environment
    Session = env["Session"]

    with Session() as first, Session() as second:
        assert reserve_inventory_write(first) is True

        # The second session uses a separate SQLite
        # connection to the same temporary database.
        assert reserve_inventory_write(second) is False

        first.rollback()

        assert reserve_inventory_write(second) is True
        second.rollback()


def test_write_reservation_after_commit(environment):
    env = environment
    Session = env["Session"]

    with Session() as first, Session() as second:
        assert reserve_inventory_write(first) is True

        vial = first.get(Vial, 1)
        vial.cap_color = "Green"

        first.commit()

        assert reserve_inventory_write(second) is True

        current = second.get(Vial, 1)
        assert current.cap_color == "Green"

        second.rollback()


def test_rollback_preserves_original_value(environment):
    env = environment

    with env["Session"]() as db:
        assert reserve_inventory_write(db) is True

        vial = db.get(Vial, 1)
        vial.lot = "UNCOMMITTED"

        db.flush()
        db.rollback()

    records = read_vials(env)

    assert records[1].lot == "ORIGINAL"


def test_preview_detects_invalid_date_sequence(environment):
    env = environment

    response = post_form(
        env["client"],
        "/vials/bulk/preview",
        payload(
            field="first_punctured_on",
            value="2026-01-01",
        ),
    )

    assert response.status_code == 422
    assert response.json()["ok"] is False

    records = read_vials(env)

    assert records[1].first_punctured_on is None
    assert audit_rows(env) == []
