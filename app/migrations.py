"""Idempotent additive SQLite migration. Back up the database before deploying."""
from sqlalchemy import inspect

def migrate(engine):
    with engine.begin() as conn:
        tables = inspect(conn).get_table_names()
        if "vials" in tables:
            cols = {c["name"] for c in inspect(conn).get_columns("vials")}
            for name, sql in {"cap_color": "VARCHAR(60) NOT NULL DEFAULT ''", "kit_ref": "VARCHAR(120) NOT NULL DEFAULT ''"}.items():
                if name not in cols:
                    conn.exec_driver_sql(f"ALTER TABLE vials ADD COLUMN {name} {sql}")
        if "coas" in tables:
            cols = {c["name"] for c in inspect(conn).get_columns("coas")}
            for name, sql in {"endotoxin_pct": "FLOAT", "job_id": "VARCHAR(120) NOT NULL DEFAULT ''", "verify_code": "VARCHAR(120) NOT NULL DEFAULT ''"}.items():
                if name not in cols:
                    conn.exec_driver_sql(f"ALTER TABLE coas ADD COLUMN {name} {sql}")
