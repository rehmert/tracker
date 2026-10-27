"""Non-destructive, repeatable SQLite schema migrations.

Always back up the live database before deploying. Legacy COA columns/tables
are retained as inert historical schema to avoid unsafe SQLite DROP COLUMN.
"""
from sqlalchemy import inspect


def migrate(engine):
    with engine.begin() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        if "compounds" in tables:
            cols = {c["name"] for c in inspect(conn).get_columns("compounds")}
            if "primary_unit" not in cols:
                conn.exec_driver_sql("ALTER TABLE compounds ADD COLUMN primary_unit VARCHAR(8) NOT NULL DEFAULT 'mg'")
            # Existing Somatropin entries are only updated when they have no vials;
            # never change a compound's established storage dimension implicitly.
            conn.exec_driver_sql("""UPDATE compounds SET primary_unit='IU'
                WHERE lower(trim(name)) IN ('somatropin', 'somatropin (hgh)', 'hgh (somatropin)')
                AND (NOT EXISTS (SELECT 1 FROM vials WHERE vials.compound_id=compounds.id)
                     OR EXISTS (SELECT 1 FROM vials WHERE vials.compound_id=compounds.id
                                AND upper(vials.content_unit)='IU'))""") if "vials" in tables else None
        if "protocols" in tables:
            pcols = {c["name"] for c in inspect(conn).get_columns("protocols")}
            if "is_active" not in pcols:
                conn.exec_driver_sql("ALTER TABLE protocols ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 0")
            for name in ("start_date", "end_date"):
                if name not in pcols:
                    conn.exec_driver_sql(f"ALTER TABLE protocols ADD COLUMN {name} DATE")
        if "protocol_items" in tables:
            icols = {c["name"] for c in inspect(conn).get_columns("protocol_items")}
            if "start_week" not in icols:
                conn.exec_driver_sql("ALTER TABLE protocol_items ADD COLUMN start_week INTEGER NOT NULL DEFAULT 1")
            if "end_week" not in icols:
                conn.exec_driver_sql("ALTER TABLE protocol_items ADD COLUMN end_week INTEGER")
        if "vials" in tables:
            cols = {c["name"] for c in inspect(conn).get_columns("vials")}
            for name, sql in {
                "cap_color": "VARCHAR(60) NOT NULL DEFAULT ''",
                "kit_ref": "VARCHAR(120) NOT NULL DEFAULT ''",
                "received_on": "DATE",
                "first_punctured_on": "DATE",
                "first_dosed_on": "DATE",
                "beyond_use_on": "DATE",
                "closed_on": "DATE",
                "storage_notes": "TEXT NOT NULL DEFAULT ''",
            }.items():
                if name not in cols:
                    conn.exec_driver_sql(f"ALTER TABLE vials ADD COLUMN {name} {sql}")
        if "coas" in tables:
            cols = {c["name"] for c in inspect(conn).get_columns("coas")}
            for name, sql in {
                "endotoxin_pct": "FLOAT",
                "job_id": "VARCHAR(120) NOT NULL DEFAULT ''",
                "verify_code": "VARCHAR(120) NOT NULL DEFAULT ''",
                "verification_status": "VARCHAR(20) NOT NULL DEFAULT 'unreviewed'",
                "verification_notes": "TEXT NOT NULL DEFAULT ''",
                "verified_at": "DATETIME",
            }.items():
                if name not in cols:
                    conn.exec_driver_sql(f"ALTER TABLE coas ADD COLUMN {name} {sql}")

        if "supplies" in tables:
            scols = {c["name"] for c in inspect(conn).get_columns("supplies")}
            for name, sql in {
                "bulk_pack_count": "INTEGER",
                "bulk_units_per_pack": "FLOAT",
                "bulk_total_cents": "INTEGER",
            }.items():
                if name not in scols:
                    conn.exec_driver_sql(f"ALTER TABLE supplies ADD COLUMN {name} {sql}")

        if "vials" not in tables or "coas" not in tables:
            return

        vcols = {c["name"] for c in inspect(conn).get_columns("vials")}
        if "coa_id" not in vcols:
            conn.exec_driver_sql(
                "ALTER TABLE vials ADD COLUMN coa_id INTEGER REFERENCES coas(id) ON DELETE SET NULL"
            )
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_vials_coa_id ON vials(coa_id)")

        # The marker prevents stale legacy links from being re-applied after a
        # user reassigns or clears a vial's COA in the new application.
        conn.exec_driver_sql("""CREATE TABLE IF NOT EXISTS tracker_schema_migrations (
            name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        marker = "coa_vial_fk_v2"
        if conn.exec_driver_sql(
            "SELECT 1 FROM tracker_schema_migrations WHERE name=?", (marker,)
        ).first():
            return

        ccols = {c["name"] for c in inspect(conn).get_columns("coas")}
        if "coa_vials" in tables:
            duplicates = conn.exec_driver_sql("""SELECT vial_id FROM coa_vials
                GROUP BY vial_id HAVING COUNT(DISTINCT coa_id)>1 LIMIT 1""").first()
            if duplicates:
                raise RuntimeError(
                    f"Vial {duplicates[0]} has multiple legacy COAs; resolve before migration"
                )
            conflicts = conn.exec_driver_sql("""SELECT cv.vial_id FROM coa_vials cv
                JOIN vials v ON v.id=cv.vial_id
                WHERE v.coa_id IS NOT NULL AND v.coa_id != cv.coa_id LIMIT 1""").first()
            if conflicts:
                raise RuntimeError(
                    f"Vial {conflicts[0]} has conflicting existing and legacy COAs"
                )
            conn.exec_driver_sql("""UPDATE vials SET coa_id=(
                SELECT cv.coa_id FROM coa_vials cv WHERE cv.vial_id=vials.id LIMIT 1)
                WHERE coa_id IS NULL AND EXISTS(
                    SELECT 1 FROM coa_vials cv WHERE cv.vial_id=vials.id)""")

        if "vial_id" in ccols:
            duplicates = conn.exec_driver_sql("""SELECT vial_id FROM coas
                WHERE vial_id IS NOT NULL GROUP BY vial_id HAVING COUNT(*)>1 LIMIT 1""").first()
            if duplicates:
                raise RuntimeError(
                    f"Vial {duplicates[0]} has multiple owner COAs; resolve before migration"
                )
            conflicts = conn.exec_driver_sql("""SELECT c.vial_id FROM coas c
                JOIN vials v ON v.id=c.vial_id
                WHERE v.coa_id IS NOT NULL AND v.coa_id != c.id LIMIT 1""").first()
            if conflicts:
                raise RuntimeError(
                    f"Vial {conflicts[0]} has conflicting legacy COA assignments"
                )
            conn.exec_driver_sql("""UPDATE vials SET coa_id=(
                SELECT c.id FROM coas c WHERE c.vial_id=vials.id LIMIT 1)
                WHERE coa_id IS NULL AND EXISTS(
                    SELECT 1 FROM coas c WHERE c.vial_id=vials.id)""")

        # Do not DROP legacy columns/tables here. Some production SQLite
        # schemas have indexes or constraints that make DROP COLUMN fail.
        # SQLAlchemy only uses vials.coa_id going forward.
        conn.exec_driver_sql(
            "INSERT INTO tracker_schema_migrations(name) VALUES (?)", (marker,)
        )
