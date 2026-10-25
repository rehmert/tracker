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

        # Move legacy COA associations to the single FK on vials. The migration
        # is transactional, repeatable, and does not discard any COA records.
        if "vials" in tables and "coas" in tables:
            vcols = {c["name"] for c in inspect(conn).get_columns("vials")}
            if "coa_id" not in vcols:
                conn.exec_driver_sql("ALTER TABLE vials ADD COLUMN coa_id INTEGER REFERENCES coas(id) ON DELETE SET NULL")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_vials_coa_id ON vials(coa_id)")
            ccols = {c["name"] for c in inspect(conn).get_columns("coas")}
            has_links = "coa_vials" in tables
            if has_links:
                # Do not silently collapse multiple different COAs for a vial.
                duplicates = conn.exec_driver_sql("SELECT vial_id FROM coa_vials GROUP BY vial_id HAVING COUNT(DISTINCT coa_id)>1 LIMIT 1").first()
                if duplicates:
                    raise RuntimeError("Multiple COAs for a vial: resolve coa_vials conflicts before migration")
                conn.exec_driver_sql("""UPDATE vials SET coa_id=(SELECT coa_id FROM coa_vials WHERE vial_id=vials.id LIMIT 1)
                    WHERE coa_id IS NULL AND EXISTS(SELECT 1 FROM coa_vials WHERE vial_id=vials.id)""")
            if "vial_id" in ccols:
                owners = conn.exec_driver_sql("SELECT vial_id FROM coas WHERE vial_id IS NOT NULL GROUP BY vial_id HAVING COUNT(*) > 1 LIMIT 1").first()
                if owners:
                    raise RuntimeError("Multiple legacy COAs belong to one vial: resolve before migration")
                # Verify that the legacy owner doesn't conflict with an existing assignment.
                conflict = conn.exec_driver_sql("""SELECT c.id FROM coas c JOIN vials v ON v.id=c.vial_id
                    WHERE v.coa_id IS NOT NULL AND v.coa_id != c.id LIMIT 1""").first()
                if conflict:
                    raise RuntimeError("Conflicting COA assignments: resolve before migration")
                conn.exec_driver_sql("""UPDATE vials SET coa_id=(SELECT id FROM coas WHERE vial_id=vials.id LIMIT 1)
                    WHERE coa_id IS NULL AND EXISTS(SELECT 1 FROM coas WHERE vial_id=vials.id)""")
                conn.exec_driver_sql("DROP INDEX IF EXISTS ix_coas_vial")
                conn.exec_driver_sql("ALTER TABLE coas DROP COLUMN vial_id")
            if has_links:
                conn.exec_driver_sql("DROP TABLE coa_vials")
