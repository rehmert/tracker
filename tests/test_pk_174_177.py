"""Behavioral concurrency and audit tests using isolated on-disk SQLite."""
from datetime import datetime
import sqlite3
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from app.db import Base
from app.models import Compound, PkScenario, PkPlannedDose, ChangeAudit
from app.pk_guarded_edit161 import CheckedEdit, update
from app.pk_scenario_version import snapshot, version

def database(tmp_path):
    path=tmp_path/'concurrency.db'
    engine=create_engine(f'sqlite:///{path}',connect_args={'timeout':0.2})
    @event.listens_for(engine,'connect')
    def fk(connection,_):
        connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        c=Compound(name='Tirzepatide')
        db.add(c);db.flush()
        s=PkScenario(compound_id=c.id,name='Concurrency test',half_life_hours=120,absorption_half_life_hours=12)
        db.add(s);db.flush()
        d=PkPlannedDose(scenario_id=s.id,planned_at=datetime(2026,11,4,8),amount_mg=2.5)
        db.add(d);db.commit()
        sid,did=s.id,d.id
    return path,engine,sid,did

def test_lock_rejects_concurrent_writer(tmp_path):
    path,engine,sid,did=database(tmp_path)
    first=sqlite3.connect(path,timeout=0.2)
    second=sqlite3.connect(path,timeout=0.2)
    try:
        first.execute('BEGIN IMMEDIATE')
        with pytest.raises(sqlite3.OperationalError,match='locked'):
            second.execute('BEGIN IMMEDIATE')
    finally:
        first.rollback();first.close();second.close();engine.dispose()

def test_stale_edit_rejected_and_audit_committed(tmp_path):
    _,engine,sid,did=database(tmp_path)
    with Session(engine) as db:
        original=version(snapshot(db,db.get(PkScenario,sid)))
    with Session(engine) as db:
        update(db,sid,CheckedEdit(dose_id=did,planned_at=datetime(2026,11,5,8),amount_mg=3,expected_version=original))
    with Session(engine) as db:
        assert db.get(PkPlannedDose,did).amount_mg==3
        assert db.scalar(select(ChangeAudit).where(ChangeAudit.action=='guarded_dose_update')) is not None
    with Session(engine) as db:
        with pytest.raises(HTTPException) as err:
            update(db,sid,CheckedEdit(dose_id=did,planned_at=datetime(2026,11,6,8),amount_mg=4,expected_version=original))
        assert err.value.status_code==409
        db.rollback()
    with Session(engine) as db:
        assert db.get(PkPlannedDose,did).amount_mg==3
    engine.dispose()
