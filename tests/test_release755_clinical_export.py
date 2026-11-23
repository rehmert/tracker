"""Release 755: synthetic-only coverage for expanded clinical progress export."""
from __future__ import annotations
from datetime import date, timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

from app.progress_export754 import extract, canonical, semantic_digest
from app.progress_clinical755 import clean_text

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "tracker_progress_sync755",
    ROOT / "scripts/tracker_progress_sync754.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


@pytest.fixture
def clinical_db(tmp_path):
    path = tmp_path / "synthetic-clinical.db"
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE tracker_progress_synthetic754 (marker TEXT NOT NULL);
        INSERT INTO tracker_progress_synthetic754 VALUES ('TRACKER_SYNTHETIC_DATA_754');
        CREATE TABLE vital_readings (measured_at TEXT, weight_kg REAL,
            systolic INTEGER, diastolic INTEGER, pulse_bpm INTEGER);
        CREATE TABLE lab_reports (
            id INTEGER PRIMARY KEY, drawn_on TEXT, notes TEXT,
            original_name TEXT, lab_name TEXT);
        CREATE TABLE lab_results (
            id INTEGER PRIMARY KEY, report_id INTEGER, analyte TEXT,
            value REAL, unit TEXT, ref_low REAL, ref_high REAL, note TEXT);
        CREATE TABLE regimen_items635 (
            id INTEGER PRIMARY KEY, kind TEXT, name TEXT, ingredient TEXT,
            strength TEXT, form TEXT, active INTEGER,
            instructions TEXT, purpose TEXT, prescriber TEXT, notes TEXT);
        CREATE TABLE regimen_schedules635 (
            id INTEGER PRIMARY KEY, item_id INTEGER, cadence TEXT,
            weekdays TEXT, interval_days INTEGER, start_on TEXT,
            end_on TEXT, at_time TEXT, amount TEXT, active INTEGER, meal TEXT);
        CREATE TABLE regimen_entries635 (
            id INTEGER PRIMARY KEY, item_id INTEGER, schedule_id INTEGER,
            logged_at TEXT, outcome TEXT, amount TEXT, meal TEXT, notes TEXT);
        CREATE TABLE regimen_tablet_schedule731 (
            schedule_id INTEGER PRIMARY KEY, tablet_strength_mg REAL,
            prescribed_dose_mg REAL, tablets_planned REAL);
        CREATE TABLE regimen_tablet_entry731 (
            entry_id INTEGER PRIMARY KEY, tablet_strength_mg REAL,
            prescribed_dose_mg REAL, tablets_taken REAL,
            administered_dose_mg REAL);
        CREATE TABLE compounds (
            id INTEGER PRIMARY KEY, name TEXT, category TEXT,
            primary_unit TEXT, notes TEXT);
        CREATE TABLE vials (
            id INTEGER PRIMARY KEY, compound_id INTEGER, label TEXT,
            lot TEXT, notes TEXT);
        CREATE TABLE dose_logs (
            id INTEGER PRIMARY KEY, vial_id INTEGER, taken_at TEXT,
            entered_value REAL, entered_unit TEXT, amount_base REAL,
            kind TEXT, site TEXT, notes TEXT);
        CREATE TABLE blend_components (blend_id INTEGER, compound_id INTEGER,
            source_vial_id INTEGER);
        CREATE TABLE blend_doses (
            id INTEGER PRIMARY KEY, blend_id INTEGER, taken_at TEXT,
            entered_value REAL, entered_unit TEXT, volume_ml REAL,
            kind TEXT, notes TEXT);
        CREATE TABLE protocols (
            id INTEGER PRIMARY KEY, is_active INTEGER, start_date TEXT,
            end_date TEXT, name TEXT, notes TEXT);
        CREATE TABLE protocol_items (
            id INTEGER PRIMARY KEY, protocol_id INTEGER, compound_id INTEGER,
            position INTEGER, amount_value REAL, amount_unit TEXT,
            freq_count REAL, freq_period TEXT, start_week INTEGER,
            end_week INTEGER, dose_days TEXT, dose_time TEXT);
        """)
        today = date.today()
        d = lambda x: (today-timedelta(days=x)).isoformat()
        db.execute("INSERT INTO lab_reports VALUES (1,?,?,?,?)",
                   (d(7), "SECRET LAB NOTE", "SECRET LAB FILE.pdf", "SECRET LAB FACILITY"))
        db.executemany(
            "INSERT INTO lab_results VALUES (?,?,?,?,?,?,?,?)",[
                (1,1,"Glucose",95,"mg/dL",70,99,"SECRET RESULT NOTE"),
                (2,1,"IGF-1",120,"ng/mL",80,220,"SECRET RESULT NOTE"),
                (3,1,"Estradiol",28,"pg/mL",None,None,"SECRET RESULT NOTE"),
            ])
        db.executemany("INSERT INTO regimen_items635 VALUES (?,?,?,?,?,?,?,?,?,?,?)",[
            (1,"medication","Synthetic medication","Active ingredient","10 mg",
             "tablet",1,"SECRET INSTRUCTIONS","SECRET PURPOSE","SECRET PRESCRIBER","SECRET NOTES"),
            (2,"supplement","Synthetic supplement","Magnesium","400 mg",
             "capsule",1,"SECRET INSTRUCTIONS","SECRET PURPOSE","SECRET PRESCRIBER","SECRET NOTES"),
            (3,"medication","Previous medication","Former ingredient","5 mg",
             "tablet",0,"SECRET INSTRUCTIONS","SECRET PURPOSE","SECRET PRESCRIBER","SECRET NOTES"),
        ])
        db.executemany("INSERT INTO regimen_schedules635 VALUES (?,?,?,?,?,?,?,?,?,?,?)",[
            (1,1,"daily","",None,d(30),None,"07:30","5 mg",1,"breakfast"),
            (2,2,"weekly","0,3",None,d(15),None,"","400 mg",1,""),
            (3,3,"daily","",None,d(90),d(10),"","5 mg",0,""),
        ])
        db.execute("INSERT INTO regimen_tablet_schedule731 VALUES (1,10,5,0.5)")
        db.executemany("INSERT INTO regimen_entries635 VALUES (?,?,?,?,?,?,?,?)",[
            (1,1,1,d(2),"taken","0.5 tablet","","SECRET ENTRY NOTE"),
            (2,1,1,d(1),"skipped","","","SECRET ENTRY NOTE"),
            (3,2,2,d(1),"taken","400 mg","","SECRET ENTRY NOTE"),
        ])
        db.execute("INSERT INTO regimen_tablet_entry731 VALUES (1,10,5,0.5,5)")
        db.executemany("INSERT INTO compounds VALUES (?,?,?,?,?)",[
            (1,"Synthetic peptide","peptide","mg","SECRET COMPOUND NOTE"),
            (2,"Synthetic hormone","testosterone","IU","SECRET COMPOUND NOTE"),
        ])
        db.executemany("INSERT INTO vials VALUES (?,?,?,?,?)",[
            (1,1,"SECRET VIAL IDENTIFIER","SECRET LOT","SECRET NOTE"),
            (2,2,"SECRET VIAL IDENTIFIER","SECRET LOT","SECRET NOTE"),
        ])
        db.executemany("INSERT INTO dose_logs VALUES (?,?,?,?,?,?,?,?,?)",[
            (1,1,d(2),250,"mcg",250,"dose","SECRET SITE","SECRET NOTE"),
            (2,2,d(1),1,"IU",1,"dose","SECRET SITE","SECRET NOTE"),
            (3,1,d(1),100,"mcg",100,"waste","SECRET SITE","SECRET NOTE"),
        ])
        db.executemany("INSERT INTO blend_components VALUES (?,?,?)",[
            (1,1,1),(1,2,2),
        ])
        db.execute("INSERT INTO blend_doses VALUES (?,?,?,?,?,?,?,?)",
                   (1,1,d(3),10,"units",0.1,"dose","SECRET BLEND NOTE"))
        db.execute("INSERT INTO protocols VALUES (1,?,?,?,?,?)",
                   (1,d(30),None,"SECRET PROTOCOL NAME","SECRET PROTOCOL NOTE"))
        db.execute("INSERT INTO protocol_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                   (1,1,1,0,250,"mcg",3,"week",1,None,"0,2,4","22:00"))
    return path


def extract_all(path, **overrides):
    params = dict(instance="DEV-SYNTHETIC", days=365,
                  export_all_labs=True, export_all_regimens=True,
                  export_all_compounds=True)
    params.update(overrides)
    return extract(path, **params)


def test_755_complete_labs_and_reference_ranges(clinical_db):
    data = extract_all(clinical_db)["labs"]["data"]
    assert data["selection"]=="all_numeric_results"
    assert data["allowlist_applied"] is False
    assert {x["analyte"] for x in data["history"]} == {
        "Glucose","IGF-1","Estradiol"}
    assert next(x for x in data["history"] if x["analyte"]=="Glucose")["reference_low"]==70
    assert next(x for x in data["history"] if x["analyte"]=="Estradiol")["reference_high"] is None


def test_755_regimen_includes_supplements_inactive_plans_and_logged_outcomes(clinical_db):
    events=extract_all(clinical_db)["interventions"]["data"]["history"]
    schedules=[x for x in events if x["type"]=="recorded_schedule"]
    logs=[x for x in events if x["type"]=="regimen_log"]
    assert {x["category"] for x in schedules} == {"medication","supplement"}
    assert len(schedules)==3 and len(logs)==3
    assert any(x["name"]=="Previous medication" and x["active_item"] is False for x in schedules)
    assert any(x["category"]=="supplement" and x["outcome"]=="taken" for x in logs)
    assert any(x["outcome"]=="skipped" for x in logs)
    assert next(x for x in logs if x["name"]=="Synthetic medication" and
                x["outcome"]=="taken")["administered_dose_mg"]==5
    planned=next(x for x in schedules if x["name"]=="Synthetic medication")
    assert planned["tablets_planned"]==0.5
    assert planned["certainty"]=="recorded_plan_not_confirmed_administration"


def test_755_compound_vial_blend_and_active_protocol_events(clinical_db):
    events=extract_all(clinical_db)["interventions"]["data"]["history"]
    actual=[x for x in events if x["type"]=="recorded_compound_dose"]
    blend=[x for x in events if x["type"]=="recorded_blend_dose"]
    plans=[x for x in events if x["type"]=="active_protocol_plan"]
    assert len(actual)==2 and {x["name"] for x in actual}=={
        "Synthetic peptide","Synthetic hormone"}
    assert all(x["certainty"]=="recorded_administration" for x in actual)
    assert next(x for x in actual if x["name"]=="Synthetic hormone")["tracked_base_unit"]=="IU"
    assert len(blend)==1 and set(blend[0]["compounds"])=={
        "Synthetic peptide","Synthetic hormone"}
    assert blend[0]["recorded_unit"]=="units"
    assert len(plans)==1
    assert plans[0]["certainty"]=="active_what_if_plan_not_confirmed_administration"
    assert not any("waste" in str(x) for x in events)


def test_755_no_documents_prescribers_vendor_vial_identifiers_or_notes(clinical_db):
    serial=canonical(extract_all(clinical_db)).decode("utf-8")
    for forbidden in ("SECRET", "purchase", "vial_id", "source_vial_id",
                      "prescriber", "attachment", "original_name",
                      "source_document", "site"):
        assert forbidden not in serial
    assert '"schema_version":"2"' in serial


def test_755_read_only_real_snapshot_does_not_mutate_fixture(clinical_db):
    original=hashlib.sha256(clinical_db.read_bytes()).hexdigest()
    payload=extract_all(clinical_db)
    assert hashlib.sha256(clinical_db.read_bytes()).hexdigest()==original
    assert sync.validate_datasets(payload)
    schema=json.loads((ROOT/"app/progress_schema755.json").read_text())
    for doc in payload.values():
        sync.validate_schema(doc, schema)


def test_755_new_opt_ins_default_off_on_legacy_config(clinical_db, tmp_path):
    p=tmp_path/"config.json"
    legacy={"schema_version":1,"repository":sync.REPOSITORY,"days":365,
            "lab_allowlist":[],"medication_allowlist":[],
            "token_file":str(tmp_path/"token"),"prod_approved":True}
    p.write_text(json.dumps(legacy));p.chmod(0o600)
    configuration=sync.config_from(p)
    assert not any(configuration[k] for k in sync.CLINICAL_FLAGS_755)
    data=extract(clinical_db,instance="DEV-SYNTHETIC")
    assert data["labs"]["data"]["history"]==[]
    assert data["interventions"]["data"]["history"]==[]


@pytest.mark.parametrize("flag",("export_all_labs","export_all_regimens","export_all_compounds"))
def test_755_only_explicit_booleans_enable_oversharing(tmp_path,flag):
    p=tmp_path/"config.json"
    c={"schema_version":1,"repository":sync.REPOSITORY,"days":365,
       "lab_allowlist":[],"medication_allowlist":[],
       "token_file":str(tmp_path/"token"),"prod_approved":False,
       flag:"yes"}
    p.write_text(json.dumps(c));p.chmod(0o600)
    with pytest.raises(ValueError,match="CONFIG_INVALID"):
        sync.config_from(p)
    c[flag]=True;p.write_text(json.dumps(c))
    assert sync.config_from(p)[flag] is True


def test_755_opt_in_independent_flags(clinical_db):
    labs=extract_all(clinical_db,export_all_regimens=False,export_all_compounds=False)
    assert len(labs["labs"]["data"]["history"])==3
    assert labs["interventions"]["data"]["history"]==[]
    meds=extract_all(clinical_db,export_all_labs=False,export_all_compounds=False)
    assert meds["labs"]["data"]["history"]==[]
    assert all(x["type"] in ("recorded_schedule","regimen_log")
               for x in meds["interventions"]["data"]["history"])
    compounds=extract_all(clinical_db,export_all_labs=False,export_all_regimens=False)
    assert all(x["type"] in (
        "recorded_compound_dose","recorded_blend_dose","active_protocol_plan")
        for x in compounds["interventions"]["data"]["history"])


def test_755_schema_v2_manifest_publication_rules(clinical_db):
    output=extract_all(clinical_db)
    files,digest=sync.documents_for(
        output,(ROOT/"app/progress_schema755.json").read_text())
    assert "schema/progress-v2.schema.json" in files
    assert "schema/progress-v1.schema.json" not in files
    manifest=json.loads(files["manifest.json"])
    assert manifest["schema_version"]=="2"
    assert manifest["source_instance"]=="DEV-SYNTHETIC"
    assert manifest["content_sha256"]==semantic_digest(output)
    assert len(manifest["files"])==8


def test_755_invalid_control_character_lab_label_is_not_exported(clinical_db):
    with sqlite3.connect(clinical_db) as db:
        db.execute("INSERT INTO lab_results VALUES (8,1,?,?,?,?,?)",
                   ("Unsafe\nlabel",44,"u",None,None,"SECRET"))
    names={x["analyte"] for x in extract_all(clinical_db)["labs"]["data"]["history"]}
    assert "Unsafe\nlabel" not in names


def test_755_clean_text_avoids_unstructured_free_text():
    assert clean_text("real name")=="real name"
    assert clean_text("bad\nname") is None
    assert clean_text(" " * 15) is None
    assert clean_text("x" * 200) is None


def test_755_unitless_numerical_lab_is_preserved(clinical_db):
    with sqlite3.connect(clinical_db) as db:
        db.execute("INSERT INTO lab_results VALUES (9,1,?,?,?,?,?)",
                   ("Unitless ratio",1.7,"",None,None,"SECRET"))
    history=extract_all(clinical_db)["labs"]["data"]["history"]
    ratio=next(x for x in history if x["analyte"]=="Unitless ratio")
    assert ratio["value"]==1.7
    assert ratio["unit"] is None


def test_755_non_numeric_lab_results_do_not_leak(clinical_db):
    with sqlite3.connect(clinical_db) as db:
        db.execute("INSERT INTO lab_results VALUES (11,1,?,?,?,?,?)",
                   ("Non numeric", "not available","mmol/L",None,None,"SECRET"))
    history=extract_all(clinical_db)["labs"]["data"]["history"]
    assert not any(x["analyte"]=="Non numeric" for x in history)


def test_755_unauthorized_new_clinical_fields_fail_publication_gate(clinical_db):
    output=extract_all(clinical_db)
    assert sync.validate_datasets(output)
    output["labs"]["data"]["history"][0]["physician_phone"]="NOT_ALLOWED"
    with pytest.raises(ValueError,match="LAB_EXPORT_FIELD_BLOCKED"):
        sync.validate_datasets(output)
    del output["labs"]["data"]["history"][0]["physician_phone"]
    output["interventions"]["data"]["history"][0]["private_extra"]="NOT_ALLOWED"
    with pytest.raises(ValueError,match="INTERVENTION_EXPORT_FIELD_BLOCKED"):
        sync.validate_datasets(output)


def test_755_synthetic_full_cli_validates_before_publication(
        clinical_db, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TRACKER_INSTANCE","DEV")
    config=tmp_path/"config.json"
    settings={
        "schema_version":1,
        "repository":sync.REPOSITORY,
        "days":365,
        "lab_allowlist":[],
        "medication_allowlist":[],
        "token_file":str(tmp_path/"NO_TOKEN_FILE_NEEDED"),
        "prod_approved":False,
        "export_all_labs":True,
        "export_all_regimens":True,
        "export_all_compounds":True,
    }
    config.write_text(json.dumps(settings))
    config.chmod(0o600)
    result=sync.run([
        "--config",str(config),
        "--db",str(clinical_db),
        "--output",str(tmp_path/"local-only"),
        "--source","synthetic",
    ])
    output=capsys.readouterr().out
    assert result==0
    assert "PROGRESS_754_STATUS=LOCAL_VALIDATED" in output
    assert "PROGRESS_754_SCHEMA=VALIDATED" in output
    assert "PROGRESS_754_DATA_SOURCE=DEV-SYNTHETIC" in output
    assert not (tmp_path/"NO_TOKEN_FILE_NEEDED").exists()
