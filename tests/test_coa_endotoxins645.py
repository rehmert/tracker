"""Release 645 endotoxin values use EU/vial; historic percent remains untouched."""
import sqlite3

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from app.db import SessionLocal
from app.main import app
from app.migrations import migrate
from app.models import Coa


def test_645_coa_endotoxin_eu_per_vial_create_and_edit():
    with TestClient(app) as client:
        with SessionLocal() as db:
            coa = Coa(lab_name="Old percentage", stored_name="metadata-eu-645",
                      endotoxin_pct=0.8)
            db.add(coa)
            db.commit()
            cid = coa.id

        page = client.get(f"/coas/{cid}")
        assert page.status_code == 200
        assert 'name="endotoxin_eu_per_vial"' in page.text
        assert 'Endotoxins (EU/vial)' in page.text
        assert "Legacy endotoxin value" in page.text
        assert 'name="endotoxin_pct"' not in page.text

        def edit(value):
            return client.post(f"/coas/{cid}/edit", data={
                "lab_name": "Old percentage",
                "endotoxin_eu_per_vial": value,
            }, follow_redirects=False)

        assert edit("0.025").status_code == 303
        with SessionLocal() as db:
            row = db.get(Coa, cid)
            assert row.endotoxin_eu_per_vial == 0.025
            assert row.endotoxin_pct == 0.8
        for invalid in ("-0.1", "inf", "nan"):
            response = edit(invalid)
            assert response.status_code == 303
            assert "err=" in response.headers["location"]
            with SessionLocal() as db:
                assert db.get(Coa, cid).endotoxin_eu_per_vial == 0.025

        assert edit("135.5").status_code == 303  # EU/vial is NOT a percentage
        with SessionLocal() as db:
            row = db.get(Coa, cid)
            assert row.endotoxin_eu_per_vial == 135.5
            assert row.endotoxin_pct == 0.8


def test_645_additive_migration_retains_historical_percent(tmp_path):
    path = tmp_path / "legacy-coa.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE coas (id INTEGER PRIMARY KEY, endotoxin_pct FLOAT)")
        db.execute("INSERT INTO coas VALUES (1, 0.4)")
    engine = create_engine(f"sqlite:///{path}")
    try:
        migrate(engine)
        migrate(engine)  # idempotent
        columns = {c["name"] for c in inspect(engine).get_columns("coas")}
        assert "endotoxin_eu_per_vial" in columns
        with sqlite3.connect(path) as db:
            assert db.execute(
                "SELECT endotoxin_pct, endotoxin_eu_per_vial FROM coas WHERE id=1"
            ).fetchone() == (0.4, None)
    finally:
        engine.dispose()
