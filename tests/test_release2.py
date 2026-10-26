from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from app.db import Base
from app.migrations import migrate
from app.models import Protocol


def test_protocols_default_to_what_if(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'new.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        p = Protocol(name="Planning only")
        db.add(p)
        db.commit()
        db.refresh(p)
        assert p.is_active is False
        p.is_active = True
        db.commit()
        assert db.get(Protocol, p.id).is_active is True


def test_active_migration_additive_and_repeatable(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE protocols (id INTEGER PRIMARY KEY, name VARCHAR(160))")
        conn.exec_driver_sql("INSERT INTO protocols(id, name) VALUES (1, 'Existing plan')")
    migrate(engine)
    migrate(engine)
    with engine.connect() as conn:
        assert 'is_active' in {c['name'] for c in inspect(conn).get_columns('protocols')}
        assert conn.exec_driver_sql('SELECT is_active FROM protocols WHERE id=1').scalar() == 0
