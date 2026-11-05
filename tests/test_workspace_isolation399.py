"""Release 399: independent inactive workspace isolation.

These tests use temporary directories only. They never
provision or activate real Tracker accounts or live storage.
"""

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.db import Base
from app import models  # noqa: F401; register ORM tables
from app.models import Compound, Purchase, Vial
from app.user_storage388 import (
    planned_storage,
    prepare_inactive_storage,
    live_storage_for,
)


@pytest.fixture
def two_users(tmp_path):
    """Provision separate, inactive test workspaces."""
    first = prepare_inactive_storage(2, tmp_path)
    second = prepare_inactive_storage(3, tmp_path)

    engines = []

    for storage in (first, second):
        engine = create_engine(
            "sqlite:///" + str(storage.database),
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(engine)
        engines.append(engine)

    yield first, second, engines[0], engines[1]

    for engine in engines:
        engine.dispose()


def test_workspace_paths_do_not_overlap(two_users):
    first, second, _, _ = two_users

    for name in (
        "root",
        "database",
        "coa",
        "labs",
        "backups",
    ):
        assert getattr(first, name) != getattr(second, name)

    assert first.root.name == "2"
    assert second.root.name == "3"


def test_same_primary_key_does_not_cross_databases(two_users):
    first, second, engine_a, engine_b = two_users

    with Session(engine_a) as db:
        db.add(Compound(name="Workspace Two"))
        db.commit()

    with Session(engine_b) as db:
        db.add(Compound(name="Workspace Three"))
        db.commit()

    with Session(engine_a) as db:
        record_a = db.get(Compound, 1)
        assert record_a is not None
        assert record_a.name == "Workspace Two"

    with Session(engine_b) as db:
        record_b = db.get(Compound, 1)
        assert record_b is not None
        assert record_b.name == "Workspace Three"

    assert first.database != second.database


def test_changes_to_one_user_do_not_change_another(two_users):
    _, _, engine_a, engine_b = two_users

    with Session(engine_a) as db:
        db.add(Compound(name="Private Compound"))
        db.commit()

    with Session(engine_b) as db:
        count = len(
            db.scalars(select(Compound)).all()
        )
        assert count == 0

    with Session(engine_a) as db:
        obj = db.scalar(select(Compound))
        obj.notes = "Updated privately"
        db.commit()

    with Session(engine_b) as db:
        count = len(
            db.scalars(select(Compound)).all()
        )
        assert count == 0


def test_vial_foreign_keys_remain_within_workspace(two_users):
    _, _, engine_a, engine_b = two_users

    with Session(engine_a) as db:
        compound = Compound(name="User Two Vial")
        db.add(compound)
        db.flush()

        db.add(Vial(
            compound_id=compound.id,
            content_value=10,
            content_unit="mg",
            label="Private Vial",
        ))
        db.commit()

    with Session(engine_a) as db:
        assert len(db.scalars(select(Vial)).all()) == 1

    with Session(engine_b) as db:
        assert len(db.scalars(select(Vial)).all()) == 0


def test_attachment_files_are_independent(two_users):
    first, second, _, _ = two_users

    common_name = "same-stored-name.pdf"

    (first.coa / common_name).write_bytes(
        b"workspace-two-coa"
    )
    (second.coa / common_name).write_bytes(
        b"workspace-three-coa"
    )

    assert (
        first.coa / common_name
    ).read_bytes() == b"workspace-two-coa"

    assert (
        second.coa / common_name
    ).read_bytes() == b"workspace-three-coa"

    assert first.coa != second.coa


def test_laboratory_attachments_are_independent(two_users):
    first, second, _, _ = two_users

    name = "lab-upload.pdf"

    (first.labs / name).write_bytes(b"private-lab-2")
    (second.labs / name).write_bytes(b"private-lab-3")

    assert (
        first.labs / name
    ).read_bytes() != (
        second.labs / name
    ).read_bytes()


def test_workspace_data_survives_independent_reopen(two_users):
    first, second, engine_a, engine_b = two_users

    with Session(engine_a) as db:
        db.add(Compound(name="Reopen Two"))
        db.commit()

    with Session(engine_b) as db:
        db.add(Compound(name="Reopen Three"))
        db.commit()

    with sqlite3.connect(first.database) as db:
        names = db.execute(
            "SELECT name FROM compounds"
        ).fetchall()
        assert names == [("Reopen Two",)]

    with sqlite3.connect(second.database) as db:
        names = db.execute(
            "SELECT name FROM compounds"
        ).fetchall()
        assert names == [("Reopen Three",)]


def test_inactive_databases_cannot_be_used_live(two_users):
    for user_id in (2, 3):
        with pytest.raises(PermissionError):
            live_storage_for(user_id)


def test_storage_plan_does_not_use_username(tmp_path):
    first = planned_storage(2, tmp_path)

    assert first.database == (
        tmp_path / "users" / "2" / "tracker.db"
    )


def test_no_administrator_data_is_provisioned(two_users):
    first, second, _, _ = two_users

    root = first.root.parent.parent

    assert not (root / "tracker.db").exists()
    assert first.root != root
    assert second.root != root


def test_users_cannot_share_upload_root(two_users):
    first, second, _, _ = two_users

    assert first.coa.is_relative_to(first.root)
    assert second.coa.is_relative_to(second.root)

    assert not first.coa.is_relative_to(second.root)
    assert not second.coa.is_relative_to(first.root)


def test_invalid_user_ids_still_fail(tmp_path):
    for bad in (0, -1, "2", "../2", True, None):
        with pytest.raises(ValueError):
            planned_storage(bad, tmp_path)
