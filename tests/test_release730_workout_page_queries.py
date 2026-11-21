"""Release 730: the Workout page makes a bounded number of SQL reads."""
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.db import Base
from app.routers import workouts654
from app.workout_models654 import (
    WorkoutEquipment654, WorkoutSession654, WorkoutSet654,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def isolated_db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            yield engine, db
    finally:
        engine.dispose()


def _machine(number):
    return WorkoutEquipment654(
        gym="730 synthetic gym", name=f"Machine {number:02d}",
        kind="selectorized",
    )


def _load(db, engine, monkeypatch):
    monkeypatch.setattr(
        workouts654, "render",
        lambda request, template, **data: {"template": template, **data},
    )
    reads = []

    def trace(conn, cursor, statement, params, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            reads.append(statement)

    event.listen(engine, "before_cursor_execute", trace)
    try:
        result = workouts654.workouts654(request=None, db=db)
    finally:
        event.remove(engine, "before_cursor_execute", trace)
    return result, reads


@pytest.mark.parametrize("machine_count", [1, 5, 40])
def test_730_latest_sets_keep_order_and_sql_count_constant(
    isolated_db, monkeypatch, machine_count,
):
    engine, db = isolated_db
    machines = [_machine(i) for i in range(machine_count)]
    db.add_all(machines)
    at = datetime(2026, 11, 20, 10)
    session = WorkoutSession654(
        started_at=at, completed_at=at + timedelta(hours=1),
    )
    db.add(session)
    db.flush()
    ids = [m.id for m in machines]
    expected = {ids[0]: None}
    for index, machine_id in enumerate(ids[1:], start=1):
        early = WorkoutSet654(
            session_id=session.id, equipment_id=machine_id,
            performed_at=at, weight_lb=60 + index, reps=8,
        )
        recent = WorkoutSet654(
            session_id=session.id, equipment_id=machine_id,
            performed_at=at + timedelta(minutes=20),
            weight_lb=80 + index, reps=10,
        )
        tie = WorkoutSet654(
            session_id=session.id, equipment_id=machine_id,
            performed_at=at + timedelta(minutes=20),
            weight_lb=90 + index, reps=7,
        )
        db.add_all([early, recent, tie])
        db.flush()
        expected[machine_id] = tie.id
    db.commit()
    db.expunge_all()

    result, reads = _load(db, engine, monkeypatch)
    assert result["template"] == "workouts654.html"
    assert set(result["latest"]) == set(ids)
    assert {
        machine_id: (item.id if item else None)
        for machine_id, item in result["latest"].items()
    } == expected
    assert len(reads) <= 6, f"SQL reads grew with machine count: {len(reads)}"
    assert sum("row_number()" in query.lower() for query in reads) == 1


def test_730_active_counts_and_unfinished_latest_not_lost(
    isolated_db, monkeypatch,
):
    engine, db = isolated_db
    first, second = _machine(1), _machine(2)
    db.add_all([first, second])
    active = WorkoutSession654(started_at=datetime(2026, 11, 20, 12))
    db.add(active)
    db.flush()
    first_id, second_id, session_id = first.id, second.id, active.id
    db.add_all([
        WorkoutSet654(
            session_id=session_id, equipment_id=first_id,
            weight_lb=100, reps=8, performed_at=active.started_at,
        ),
        WorkoutSet654(
            session_id=session_id, equipment_id=first_id,
            weight_lb=110, reps=6,
            performed_at=active.started_at + timedelta(minutes=1),
        ),
    ])
    db.commit()
    db.expunge_all()

    result, reads = _load(db, engine, monkeypatch)
    assert result["active"].id == session_id
    assert result["counts_this_session"] == {first_id: 2, second_id: 0}
    assert result["latest"][first_id].weight_lb == 110
    assert result["latest"][second_id] is None
    assert len(reads) <= 10
    assert sum("row_number()" in query.lower() for query in reads) == 1


def test_730_read_path_is_scoped_and_has_no_mutations():
    source = (ROOT / "app/routers/workouts654.py").read_text()
    read_path = source.split("def workouts654(", 1)[1].split(
        "\n\n@router.post", 1
    )[0]
    assert "func.row_number().over(" in read_path
    assert "ranked.c.set_rank == 1" in read_path
    assert "Counter(entry.equipment_id for entry in rows)" in read_path
    assert "item.id: db.scalar(" not in read_path
    assert "get_scoped_db390" in source
    assert "db.add(" not in read_path
    assert "db.commit(" not in read_path
    assert "db.delete(" not in read_path
