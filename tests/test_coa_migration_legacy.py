"""Regression tests for older production COA schema upgrades."""
from sqlalchemy import create_engine
from app.migrations import migrate


def test_legacy_coa_migration_is_nondestructive_and_one_time(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE vials (id INTEGER PRIMARY KEY)")
        conn.exec_driver_sql("CREATE TABLE coas (id INTEGER PRIMARY KEY, vial_id INTEGER REFERENCES vials(id))")
        conn.exec_driver_sql("CREATE INDEX ix_coas_vial ON coas(vial_id)")
        conn.exec_driver_sql("CREATE TABLE coa_vials (coa_id INTEGER, vial_id INTEGER)")
        conn.exec_driver_sql("INSERT INTO vials(id) VALUES (1), (2), (3)")
        conn.exec_driver_sql("INSERT INTO coas(id,vial_id) VALUES (10,1), (20,NULL)")
        conn.exec_driver_sql("INSERT INTO coa_vials(coa_id,vial_id) VALUES (20,2)")
    migrate(engine)
    with engine.begin() as conn:
        assert conn.exec_driver_sql("SELECT id,coa_id FROM vials ORDER BY id").all() == [(1,10),(2,20),(3,None)]
        assert conn.exec_driver_sql("SELECT vial_id FROM coas WHERE id=10").scalar() == 1
        conn.exec_driver_sql("UPDATE vials SET coa_id=NULL WHERE id=1")
        conn.exec_driver_sql("UPDATE vials SET coa_id=10 WHERE id=2")
    migrate(engine)
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT id,coa_id FROM vials ORDER BY id").all() == [(1,None),(2,10),(3,None)]


def test_migration_detects_conflicting_legacy_assignments(tmp_path):
    import pytest
    engine = create_engine(f"sqlite:///{tmp_path / 'conflict.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE vials (id INTEGER PRIMARY KEY)")
        conn.exec_driver_sql("CREATE TABLE coas (id INTEGER PRIMARY KEY, vial_id INTEGER)")
        conn.exec_driver_sql("CREATE TABLE coa_vials (coa_id INTEGER, vial_id INTEGER)")
        conn.exec_driver_sql("INSERT INTO vials VALUES (1)")
        conn.exec_driver_sql("INSERT INTO coas VALUES (10,NULL), (20,NULL)")
        conn.exec_driver_sql("INSERT INTO coa_vials VALUES (10,1), (20,1)")
    with pytest.raises(RuntimeError, match="multiple legacy COAs"):
        migrate(engine)
