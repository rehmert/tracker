from sqlalchemy import create_engine, inspect
from app.db import Base
from app import models
from app.migrations import migrate


def test_lifecycle_schema_new_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'tracker.db'}")
    migrate(engine)
    Base.metadata.create_all(engine)
    names = {c['name'] for c in inspect(engine).get_columns('vials')}
    assert {'received_on','first_punctured_on','first_dosed_on','beyond_use_on','closed_on','storage_notes'} <= names


def test_lifecycle_schema_upgrade(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE vials (id INTEGER PRIMARY KEY, cap_color VARCHAR(60), kit_ref VARCHAR(120))')
    migrate(engine)
    names = {c['name'] for c in inspect(engine).get_columns('vials')}
    assert 'beyond_use_on' in names and 'storage_notes' in names
