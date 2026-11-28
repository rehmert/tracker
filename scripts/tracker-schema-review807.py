#!/usr/bin/env python3
"""Review the exact 807 additive schema; never mutate the installed database."""
import argparse
import ast
from pathlib import Path
import subprocess

BASE = "2d597a9907ab3c7e1915f073ed5cd5e898e93b90"
EXPECTED = {"wellness_preferences807", "wellness_days807", "wellness_symptoms807",
            "site_reactions807", "administration_context807", "rotation_preferences807",
            "site_exclusions807", "goal_milestone_preferences807"}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    def git(*command):
        return subprocess.check_output(["git", "-C", str(args.root), *command], text=True).strip()
    if args.base != BASE or git("rev-parse", "HEAD") != args.target:
        raise SystemExit("Invalid exact 807 schema baseline or candidate")
    git("merge-base", "--is-ancestor", BASE, args.target)
    changed = set(git("diff", "--name-only", BASE, args.target).splitlines())
    schema = "app/wellness_models807.py"
    if schema not in changed:
        raise SystemExit("Missing reviewed wellness model")
    for path in changed:
        if path != schema and (path.startswith(("deploy/", "alembic/", "requirements"))
                or path in ("app/db.py", "app/models.py", "app/migrations.py")
                or ("models" in Path(path).stem and path.startswith("app/"))):
            raise SystemExit("Unexpected schema or deployment path: " + path)
    tree = ast.parse((args.root / schema).read_text())
    tables = {node.value.value for node in ast.walk(tree)
              if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name)
              and t.id == "__tablename__" for t in node.targets)
              and isinstance(node.value, ast.Constant)}
    if tables != EXPECTED:
        raise SystemExit("Unexpected additive table set")
    from app.db import Base
    from app import models, wellness_models807
    import sqlalchemy
    engine = sqlalchemy.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        legacy = [t for t in Base.metadata.sorted_tables if t.name not in EXPECTED]
        Base.metadata.create_all(conn, tables=legacy)
        before = set(sqlalchemy.inspect(conn).get_table_names())
        Base.metadata.create_all(conn)
        Base.metadata.create_all(conn)
        after = set(sqlalchemy.inspect(conn).get_table_names())
        if after - before != EXPECTED or before - after:
            raise SystemExit("Schema is not additive")
        if conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
            raise SystemExit("Foreign key validation failed")
    print("RELEASE_807_SCHEMA_REVIEW=PASSED")

if __name__ == "__main__":
    main()
