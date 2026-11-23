#!/usr/bin/env python3
"""Generate genuinely synthetic, owner-only fixture data for DEV rehearsal.

No live Tracker tables are accessed, no attachment content is read.
"""
from datetime import date, timedelta
import os
from pathlib import Path
import sqlite3
import sys
import json

def main():
    if (os.geteuid() != 0 or
            os.environ.get("TRACKER_INSTANCE", "").upper() != "DEV"):
        raise SystemExit("FIXTURE_754_DEV_ROOT_ONLY")
    if len(sys.argv) != 2:
        raise SystemExit("Expected one target database pathname")
    dest = Path(sys.argv[1]).absolute()
    if dest.is_symlink() or dest.exists():
        raise SystemExit("FIXTURE_754_REFUSE_OVERWRITE")
    dest.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if dest.parent.stat().st_mode & 0o077:
        raise SystemExit("FIXTURE_754_DIRECTORY_NOT_PRIVATE")
    db = sqlite3.connect(dest)
    os.chmod(dest, 0o600)
    try:
        db.executescript("""
        CREATE TABLE tracker_progress_synthetic754 (marker TEXT NOT NULL);
        INSERT INTO tracker_progress_synthetic754 VALUES ('TRACKER_SYNTHETIC_DATA_754');
        CREATE TABLE vital_readings (measured_at TEXT, weight_kg REAL,
          systolic INTEGER, diastolic INTEGER, pulse_bpm INTEGER);
        CREATE TABLE workout_sessions654 (id INTEGER PRIMARY KEY, started_at TEXT,
          completed_at TEXT);
        CREATE TABLE workout_equipment654 (id INTEGER PRIMARY KEY, name TEXT,
          kind TEXT, manufacturer TEXT, model TEXT);
        CREATE TABLE workout_sets654 (id INTEGER PRIMARY KEY,
          session_id INTEGER, equipment_id INTEGER, weight_lb REAL,
          reps INTEGER, performed_at TEXT);
        CREATE TABLE workout_set_types667 (set_id INTEGER, set_type TEXT);
        CREATE TABLE tracker_food_products (id INTEGER PRIMARY KEY, nutrients TEXT);
        CREATE TABLE tracker_food_entries (product_id INTEGER, eaten_on TEXT, servings REAL);
        CREATE TABLE tracker_food_targets (nutrient TEXT, value REAL);
        CREATE TABLE lab_reports (id INTEGER PRIMARY KEY, drawn_on TEXT);
        CREATE TABLE lab_results (report_id INTEGER, analyte TEXT,
          value REAL, unit TEXT, ref_low REAL, ref_high REAL);
        CREATE TABLE regimen_items635 (id INTEGER PRIMARY KEY, kind TEXT, name TEXT);
        CREATE TABLE regimen_schedules635 (item_id INTEGER, start_on TEXT, end_on TEXT,
          amount TEXT, cadence TEXT);
        """)
        now=date.today()
        d=lambda x:(now-timedelta(days=x)).isoformat()
        db.executemany("INSERT INTO vital_readings VALUES (?,?,?,?,?)",[
            (d(30),98,128,80,70),(d(7),96,123,77,69),(d(2),95,120,76,67)])
        db.execute("INSERT INTO workout_equipment654 VALUES (1,?,?,?,?)",
                   ("Synthetic chest press", "selectorized", "Fixture", "Model A"))
        db.execute("INSERT INTO workout_sessions654 VALUES (1,?,?)",(d(2),d(2)))
        db.execute("INSERT INTO workout_sets654 VALUES (1,?,?,?,?,?)",
                   (1,1,90,10,d(2)))
        db.execute("INSERT INTO workout_set_types667 VALUES (1,'working')")
        db.execute("INSERT INTO tracker_food_products VALUES (1,?)",(
            json.dumps({"energy":350,"proteins":35,"carbohydrates":25,"fat":6}),))
        db.execute("INSERT INTO tracker_food_entries VALUES (?,?,?)",
                   (1,d(2),2))
        db.execute("INSERT INTO tracker_food_targets VALUES ('proteins',60)")
        db.execute("INSERT INTO lab_reports VALUES (1,?)",(d(3),))
        db.execute("INSERT INTO lab_results VALUES (1,?,?,?,?,?)",
                   ("Glucose",88,"mg/dL",70,99))
        db.execute("INSERT INTO regimen_items635 VALUES (1,?,?)",
                   ("medication","Synthetic treatment"))
        db.execute("INSERT INTO regimen_schedules635 VALUES (1,?,?,?,?)",
                   (d(20),None,"1 unit","weekly"))
        db.commit()
    finally:
        db.close()
    print("PROGRESS_754_SYNTHETIC_FIXTURE=CREATED")

if __name__ == "__main__":
    main()
