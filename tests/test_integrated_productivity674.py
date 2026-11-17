"""Release 674 focused tests for productivity workflows."""
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Coa, Purchase
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from app.workout_models667 import WorkoutSetType667
from app.workout_models668 import WorkoutSetCorrection668
from app.workout_progression674 import progression_for674
from app.daily_summary674 import snapshot674
from app.routers.data_quality674 import quality_summary674
from app.routers.recovery674 import undo_last_correction674

ROOT = Path(__file__).resolve().parents[1]


def test_674_progression_ignores_warmups_and_never_writes(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "progression.sqlite"))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        machine = WorkoutEquipment654(name="Chest Press", kind="selectorized")
        session = WorkoutSession654(started_at=datetime.now(), completed_at=datetime.now())
        db.add_all([machine, session])
        db.flush()
        for load, count, warmup in ((100, 10, False), (100, 11, False),
                                    (100, 10, False), (200, 20, True)):
            row = WorkoutSet654(session_id=session.id, equipment_id=machine.id,
                                weight_lb=load, reps=count)
            db.add(row)
            db.flush()
            if warmup:
                db.add(WorkoutSetType667(set_id=row.id, set_type="warmup"))
        db.commit()
        before = [(r.id, r.weight_lb, r.reps) for r in db.scalars(
            select(WorkoutSet654).order_by(WorkoutSet654.id))]
        recommended = progression_for674(db, machine.id, 10)
        assert recommended["progressed"] is True
        assert (recommended["weight"], recommended["reps"]) == (105.0, 10)
        assert progression_for674(db, machine.id, 12)["progressed"] is False
        after = [(r.id, r.weight_lb, r.reps) for r in db.scalars(
            select(WorkoutSet654).order_by(WorkoutSet654.id))]
        assert before == after


def test_674_undo_preserves_audit_and_rejects_repeat(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "undo.sqlite"))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        machine = WorkoutEquipment654(name="Row", kind="selectorized")
        session = WorkoutSession654(started_at=datetime.now(), completed_at=datetime.now())
        db.add_all([machine, session])
        db.flush()
        row = WorkoutSet654(session_id=session.id, equipment_id=machine.id,
                            weight_lb=125, reps=10, effort=6)
        db.add(row)
        db.commit()
        from app.routers.workouts668 import correct_recorded_set668
        result = correct_recorded_set668(session.id, row.id, weight_lb=130, reps=9,
            effort="7", set_type="warmup", reason="Correct entered load", db=db)
        assert result.status_code == 303
        audit = db.scalar(select(WorkoutSetCorrection668))
        assert audit
        assert undo_last_correction674(db, session.id, row.id, audit.id) is None
        db.refresh(row)
        assert (row.weight_lb, row.reps, row.effort) == (125, 10, 6)
        assert db.get(WorkoutSetType667, row.id) is None
        all_audits = list(db.scalars(select(WorkoutSetCorrection668)))
        assert len(all_audits) == 2
        assert any(x.reason == f"Undo of correction #{audit.id}" for x in all_audits)
        assert undo_last_correction674(db, session.id, row.id, audit.id) is not None
        assert len(list(db.scalars(select(WorkoutSetCorrection668)))) == 2


def test_674_undo_fails_closed_when_values_have_changed(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "stale.sqlite"))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        machine = WorkoutEquipment654(name="Row", kind="selectorized")
        session = WorkoutSession654(started_at=datetime.now(), completed_at=datetime.now())
        db.add_all([machine, session])
        db.flush()
        row = WorkoutSet654(session_id=session.id, equipment_id=machine.id,
                            weight_lb=120, reps=9)
        db.add(row)
        db.flush()
        change = WorkoutSetCorrection668(set_id=row.id,
            old_weight_lb=110, new_weight_lb=120, old_reps=10, new_reps=9,
            old_effort=None, new_effort=None,
            old_type="working", new_type="working", reason="Original correction")
        db.add(change)
        db.commit()
        row.weight_lb = 130
        db.commit()
        assert "changed" in undo_last_correction674(db, session.id, row.id, change.id)
        assert row.weight_lb == 130
        assert len(list(db.scalars(select(WorkoutSetCorrection668)))) == 1


def test_674_quality_and_daily_snapshot_do_not_mutate(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "quality.sqlite"))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Coa(lab_name="", original_name="", tested_on=None))
        db.add(Purchase(vendor="Example Vendor", purchased_on=date.today()))
        db.add(WorkoutEquipment654(name="Unmapped Machine", kind="selectorized"))
        db.commit()
        report = quality_summary674(db)
        assert report["counts"]["COA"] >= 1
        assert report["counts"]["Purchase"] >= 1
        assert report["counts"]["Workout"] >= 1
        assert all(x["href"].startswith("/") for x in report["issues"])
        snapshot = snapshot674(db, date.today())
        assert snapshot["workout_today"] == 0
        assert snapshot["food"]["available"] is False
        assert db.scalar(select(Purchase)).vendor == "Example Vendor"


def test_674_templates_routes_and_no_auto_log_contract():
    for name in ("base.html", "mobile_today509.html", "data_quality674.html",
                 "workout_quick659.html", "workout_corrections668.html"):
        Environment().parse((ROOT / "app/templates" / name).read_text())
    main = (ROOT / "app/main.py").read_text()
    assert "app.include_router(data_quality674.router)" in main
    assert "app.include_router(recovery674.router)" in main
    today = (ROOT / "app/templates/mobile_today509.html").read_text()
    assert "Daily Command Center" in today and "/data-quality" in today
    history = (ROOT / "app/templates/workout_corrections668.html").read_text()
    assert "Undo this correction" in history
    gym = (ROOT / "app/templates/workout_quick659.html").read_text()
    assert 'id="workout674-use-progression"' in gym
    js = (ROOT / "app/static/js/tracker-workout-progression674.js").read_text()
    assert 'addEventListener("click"' in js
    assert "fetch(" not in js and "requestSubmit(" not in js
    css = (ROOT / "app/static/css/tracker-productivity674.css").read_text()
    assert css.count("{") == css.count("}")
