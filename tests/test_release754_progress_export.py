"""Release 754: synthetic-only fixtures verify privacy, data, and publisher."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
from datetime import date, timedelta

import pytest

from app.progress_export754 import extract, semantic_digest, canonical, CATEGORIES

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "tracker_progress_sync754", ROOT / "scripts/tracker_progress_sync754.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


@pytest.fixture
def fixture_db(tmp_path):
    path = tmp_path / "synthetic.db"
    with sqlite3.connect(path) as db:
        db.executescript("""
          CREATE TABLE vital_readings (
            measured_at TEXT, weight_kg REAL, systolic INTEGER,
            diastolic INTEGER, pulse_bpm INTEGER,
            notes TEXT, context TEXT, email TEXT);
          CREATE TABLE workout_sessions654 (
            id INTEGER PRIMARY KEY, started_at TEXT, completed_at TEXT);
          CREATE TABLE workout_equipment654 (
            id INTEGER PRIMARY KEY, name TEXT, kind TEXT,
            manufacturer TEXT, model TEXT, qr_value TEXT, gym TEXT);
          CREATE TABLE workout_sets654 (
            id INTEGER PRIMARY KEY, session_id INTEGER, equipment_id INTEGER,
            weight_lb REAL, reps INTEGER, performed_at TEXT);
          CREATE TABLE workout_set_types667 (set_id INTEGER, set_type TEXT);
          CREATE TABLE tracker_food_products (
            id INTEGER PRIMARY KEY, nutrients TEXT, name TEXT, source TEXT);
          CREATE TABLE tracker_food_entries (
            product_id INTEGER, eaten_on TEXT, servings REAL, meal TEXT);
          CREATE TABLE tracker_food_targets (nutrient TEXT, value REAL);
          CREATE TABLE lab_reports (id INTEGER PRIMARY KEY, drawn_on TEXT,
                                    original_name TEXT, notes TEXT);
          CREATE TABLE lab_results (report_id INTEGER, analyte TEXT,
            value REAL, unit TEXT, ref_low REAL, ref_high REAL, note TEXT);
          CREATE TABLE regimen_items635 (
            id INTEGER PRIMARY KEY, kind TEXT, name TEXT,
            instructions TEXT, prescriber TEXT, notes TEXT);
          CREATE TABLE regimen_schedules635 (
            item_id INTEGER, start_on TEXT, end_on TEXT,
            amount TEXT, cadence TEXT);
        """)
        on = date.today()
        def ago(n):
            return (on-timedelta(days=n)).isoformat()
        db.executemany(
            "INSERT INTO vital_readings VALUES (?,?,?,?,?,?,?,?)", [
                (ago(40), 102, 122, 79, 71, "PRIVATE VITAL NOTE", "", "SENSITIVE EMAIL"),
                (ago(15), 100, 120, 78, 69, "PRIVATE", "", "SENSITIVE"),
                (ago(4), 99, 118, 75, 68, "PRIVATE", "", "SENSITIVE"),
                (ago(1), 98, 116, 74, 67, "PRIVATE", "", "SENSITIVE"),
            ])
        db.execute("INSERT INTO workout_equipment654 VALUES (1,?,?,?,?,?,?)",
                   ("Test machine", "selectorized", "Acme", "A1",
                    "SENSITIVE QR", "PRIVATE GYM"))
        db.execute("INSERT INTO workout_equipment654 VALUES (2,?,?,?,?,?,?)",
                   ("Different machine", "selectorized", "Acme", "A2",
                    "SENSITIVE QR", "PRIVATE GYM"))
        db.execute("INSERT INTO workout_sessions654 VALUES (1,?,?)",
                   (ago(2), ago(2)))
        db.execute("INSERT INTO workout_sessions654 VALUES (2,?,NULL)", (ago(1),))
        db.executemany(
            "INSERT INTO workout_sets654 VALUES (?,?,?,?,?,?)", [
              (1,1,1,100,10,ago(2)), (2,1,1,50,10,ago(2)),
              (3,1,2,180,8,ago(2)), (4,2,1,300,12,ago(1)),
            ])
        db.executemany("INSERT INTO workout_set_types667 VALUES (?,?)",
                       [(1,"working"), (2,"warmup"), (3,"working"), (4,"working")])
        db.execute("INSERT INTO tracker_food_products VALUES (1,?,?,?)",
                   (json.dumps({"energy":400,"proteins":30,
                                "carbohydrates":20,"fat":8}),
                    "PRIVATE PRODUCT NAME", "PRIVATE SOURCE"))
        db.execute("INSERT INTO tracker_food_entries VALUES (?,?,?,?)",
                   (1, ago(1), 2, "dinner"))
        db.execute("INSERT INTO tracker_food_targets VALUES ('proteins',55)")
        db.execute("INSERT INTO lab_reports VALUES (1,?,?,?)",
                   (ago(7),"PRIVATE LAB DOCUMENT","PRIVATE LAB NOTE"))
        db.execute("INSERT INTO lab_results VALUES (1,?,?,?,?,?,?)",
                   ("Glucose",93,"mg/dL",70,99,"PRIVATE LAB RESULT NOTE"))
        db.execute("INSERT INTO lab_results VALUES (1,?,?,?,?,?,?)",
                   ("Secret analyte",55,"ng/mL",None,None,"PRIVATE"))
        db.execute("INSERT INTO regimen_items635 VALUES (1,?,?,?,?,?)",
                   ("medication","Approved fixture","PRIVATE","PRIVATE","PRIVATE"))
        db.execute("INSERT INTO regimen_schedules635 VALUES (1,?,?,?,?)",
                   (ago(15),None,"1 mg","daily"))
    return path


def datasets(db, **kwargs):
    return extract(db, instance="DEV-SYNTHETIC", days=90, **kwargs)


def test_754_readonly_snapshot_does_not_modify_database(fixture_db):
    before = hashlib.sha256(fixture_db.read_bytes()).hexdigest()
    output = datasets(fixture_db)
    after = hashlib.sha256(fixture_db.read_bytes()).hexdigest()
    assert before == after
    assert set(output) == set(CATEGORIES)
    assert sync.validate_datasets(output)


def test_754_weight_and_missing_body_measurements(fixture_db):
    output = datasets(fixture_db)
    weight = output["weight"]["data"]
    assert len(weight["history"]) == 4
    assert weight["summary"]["current_weight_lb"] > 200
    assert weight["summary"]["moving_average_lb"]["7d"] is not None
    assert weight["summary"]["moving_average_lb"]["28d"] is not None
    assert weight["summary"]["change_lb"]["28d"] < 0
    assert weight["summary"]["goal_weight_lb"] is None
    assert output["body-measurements"]["data"]["waist_to_height_ratio"] is None
    assert "not_recorded" in output["body-measurements"]["data"]["status"]


def test_754_workouts_only_completed_and_equipment_scoped(fixture_db):
    output = datasets(fixture_db)
    rows = output["workouts"]["data"]["sessions"]
    assert [r["status"] for r in rows] == ["completed","in_progress"]
    machines = output["workouts"]["data"]["machine_progress"]
    assert len(machines)==2
    assert {r["equipment_id"] for r in machines} == {1,2}
    assert machines[0]["working_sets"] == 1
    assert machines[0]["volume_lb_reps"] == 1000
    assert machines[1]["volume_lb_reps"] == 1440
    assert all("gym" not in row for row in machines)


def test_754_nutrition_absence_distinct_from_zero_and_targets(fixture_db):
    report = datasets(fixture_db)["nutrition"]["data"]
    assert report["logged_days"] == 1
    assert report["daily"][-1]["totals"]["energy"] is None
    logged = next(x for x in report["daily"] if x["logged_foods"])
    assert logged["totals"]["energy"] == 800
    assert logged["totals"]["proteins"] == 60
    assert logged["protein_target_met"] is True
    assert report["daily"][-1]["totals"]["proteins"] is None


def test_754_labs_and_interventions_default_to_empty_allowlists(fixture_db):
    result = datasets(fixture_db)
    assert result["labs"]["data"]["history"] == []
    assert result["interventions"]["data"]["history"] == []
    include = datasets(fixture_db, lab_allowlist=["Glucose"],
                       medication_allowlist=["Approved fixture"])
    assert [r["analyte"] for r in include["labs"]["data"]["history"]] == ["Glucose"]
    assert len(include["interventions"]["data"]["history"]) == 1
    assert include["interventions"]["data"]["history"][0]["certainty"] == (
        "recorded_plan_not_confirmed_administration")


def test_754_no_sensitive_or_arbitrary_fields_leave_extractor(fixture_db):
    text = canonical(datasets(fixture_db, lab_allowlist=["Glucose"],
                     medication_allowlist=["Approved fixture"])).decode()
    for secret in ("PRIVATE", "SENSITIVE", "email", "password", "qr_value",
                   "original_name", "prescriber", "source_vial_id", "notes"):
        assert secret not in text, secret


def test_754_nonfinite_and_unknown_schema_rejected(fixture_db):
    data = datasets(fixture_db)
    data["vitals"]["data"]["bad"] = {"notes": "forbidden"}
    with pytest.raises(ValueError, match="FIELD_NOT_ALLOWLISTED"):
        sync.validate_datasets(data)
    data["vitals"]["data"].pop("bad")
    data["weight"]["schema_version"] = "2"
    with pytest.raises(ValueError, match="SCHEMA_INVALID"):
        sync.validate_datasets(data)


def test_754_semantic_digest_ignores_generation_timestamp_only(fixture_db):
    output = datasets(fixture_db)
    original = semantic_digest(output)
    output["overview"]["generated_at_utc"] = "2000-01-01T00:00:00Z"
    assert semantic_digest(output) == original
    output["weight"]["data"]["summary"]["goal_weight_lb"] = 215
    assert semantic_digest(output) != original


def test_754_private_repo_verification_fails_closed(monkeypatch):
    monkeypatch.setattr(sync,"_api",lambda *a,**kw:{
        "full_name":"rehmert/tracker-progress-data",
        "private":False,"visibility":"public",
        "default_branch":"main","archived":False,
    })
    with pytest.raises(ValueError, match="DESTINATION_NOT_PRIVATE"):
        sync.repo_visibility("TEST_TOKEN")


@pytest.mark.parametrize("visibility,private", [
    ("private",False),("public",True),("private",True)])
def test_754_invalid_destination_or_valid_private(monkeypatch, visibility, private):
    monkeypatch.setattr(sync,"_api",lambda *args,**kwargs:{
        "full_name":"rehmert/tracker-progress-data",
        "private":private,"visibility":visibility,
        "default_branch":"main","archived":False,
    })
    if visibility == "private" and private:
        assert sync.repo_visibility("FAKE")["private"] is True
    else:
        with pytest.raises(ValueError):
            sync.repo_visibility("FAKE")


def test_754_publish_unchanged_never_creates_commit(monkeypatch):
    observed = []
    def api(token, method, path, body=None):
        observed.append((method,path))
        if path.endswith("/git/ref/heads/main"):
            return {"object":{"sha":"a"*40}}
        if "/git/commits/" in path:
            return {"tree":{"sha":"b"*40}}
        if "/git/trees/" in path:
            return {"tree":[]}
        if "/contents/manifest.json" in path:
            return {"content": __import__("base64").b64encode(
                b'{"content_sha256":"SAME"}').decode()}
        raise AssertionError(path)
    monkeypatch.setattr(sync,"repo_visibility",lambda token: None)
    monkeypatch.setattr(sync,"_api",api)
    assert sync.publish("FAKE",{"latest/overview.json":"{}"},"SAME")=="UNCHANGED"
    assert not any(method != "GET" for method,path in observed)


def test_754_config_secret_permissions_and_allowlist_validation(tmp_path):
    config = tmp_path / "config.json"
    values = {"schema_version":1,"repository":sync.REPOSITORY,
              "days":90,"lab_allowlist":[],"medication_allowlist":[],
              "token_file":str(tmp_path/"token"),"prod_approved":False}
    config.write_text(json.dumps(values))
    config.chmod(0o600)
    assert sync.config_from(config)["days"] == 90
    config.chmod(0o644)
    with pytest.raises(ValueError, match="PRIVATE_FILE_PERMISSIONS"):
        sync.config_from(config)


def test_754_dev_synthetic_export_never_requires_github_token(
        fixture_db, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("TRACKER_INSTANCE","DEV")
    config=tmp_path/"config.json"
    values={"schema_version":1,"repository":sync.REPOSITORY,"days":90,
            "lab_allowlist":[],"medication_allowlist":[],
            "token_file":str(tmp_path/"NONEXISTENT_TOKEN"),"prod_approved":False}
    config.write_text(json.dumps(values));config.chmod(0o600)
    result=sync.run(["--config",str(config),"--db",str(fixture_db),
                     "--output",str(tmp_path/"out"),"--source","synthetic"])
    assert result == 0
    assert "PROGRESS_754_STATUS=LOCAL_VALIDATED" in capsys.readouterr().out


def test_754_prod_export_cannot_start_without_explicit_approval(
        fixture_db, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("TRACKER_INSTANCE","PROD")
    config=tmp_path/"config.json"
    values={"schema_version":1,"repository":sync.REPOSITORY,"days":90,
            "lab_allowlist":[],"medication_allowlist":[],
            "token_file":str(tmp_path/"NONEXISTENT_TOKEN"),"prod_approved":False}
    config.write_text(json.dumps(values));config.chmod(0o600)
    code=sync.run(["--config",str(config),"--db",str(fixture_db),
                   "--output",str(tmp_path/"out"),"--source","live","--sync"])
    assert code == 1
    assert "PROD_EXPORT_NOT_AUTHORIZED" in capsys.readouterr().err


def test_754_manifest_and_schema_are_predictable(fixture_db):
    result=datasets(fixture_db)
    schema=(ROOT/"app/progress_schema754.json").read_text()
    files,digest=sync.documents_for(result,schema)
    assert len(files)==len(CATEGORIES)+3
    assert set(files)==set(sync.FILENAMES.values())|{
        "README.md","manifest.json","schema/progress-v1.schema.json"}
    manifest=json.loads(files["manifest.json"])
    assert manifest["content_sha256"]==digest
    assert len(manifest["files"])==len(CATEGORIES)
