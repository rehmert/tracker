"""Release 754: explicitly allowlisted, read-only progress snapshot (stdlib only).

Never opens ORM engines, initializes tables, or serializes whole records.
Intentionally does not derive body-fat / muscle gains from scale or BIA data.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from urllib.parse import quote

from .metrics import KG_PER_LB

SCHEMA_VERSION = "1"
CATEGORIES = ("overview", "weight", "body-measurements", "workouts",
              "nutrition", "vitals", "labs", "interventions")
NUTRIENTS = {"energy": "kcal", "proteins": "g",
             "carbohydrates": "g", "fat": "g"}
SOURCE_FIELDS = {"lab_results": ("analyte", "value", "unit", "ref_low", "ref_high"),
                 "vital_readings": ("measured_at", "weight_kg", "systolic",
                                    "diastolic", "pulse_bpm")}


def _number(value):
    if value is None:
        return None
    try:
        x = float(value)
        return round(x, 4) if math.isfinite(x) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _average(values):
    return round(sum(values) / len(values), 3) if values else None


def _date(value):
    return str(value)[:10] if value is not None else None


def _tables(db):
    return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _select(db, table, sql, params=()):
    if table not in _tables(db):
        return []
    return db.execute(sql, params).fetchall()


def _roll_average(points, on, days):
    cutoff = on - timedelta(days=days-1)
    return _average([v for d, v in points if d >= cutoff])


def extract(db_path: Path, *, instance: str, days: int = 365,
            lab_allowlist=(), medication_allowlist=(), today: date | None = None):
    """Return deterministic allowlisted datasets, generated using one read txn."""
    if instance not in ("DEV-SYNTHETIC", "PROD"):
        raise ValueError("Invalid source label")
    if not 7 <= days <= 730:
        raise ValueError("Report window must be 7..730 days")
    on = today or date.today()
    start = on - timedelta(days=days - 1)
    period = {"from": start.isoformat(), "to": on.isoformat()}
    original = Path(db_path).absolute()
    if original.is_symlink():
        raise ValueError("DATABASE_SYMLINK_DISALLOWED")
    safe_path = original.resolve(strict=True)
    if not safe_path.is_file():
        raise ValueError("DATABASE_UNAVAILABLE")
    db = sqlite3.connect("file:" + quote(str(safe_path)) + "?mode=ro", uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        # The read transaction's first query pins a consistent SQLite snapshot.
        table_names = _tables(db)
        vitals = _select(db, "vital_readings", """
            SELECT measured_at, weight_kg, systolic, diastolic, pulse_bpm
            FROM vital_readings WHERE substr(measured_at,1,10) BETWEEN ? AND ?
            ORDER BY measured_at
        """, (period["from"], period["to"]))
        first = _select(db, "vital_readings", """
            SELECT measured_at, weight_kg FROM vital_readings
            WHERE weight_kg IS NOT NULL ORDER BY measured_at LIMIT 1
        """)
        weight = []
        bp = []
        for row in vitals:
            day = _date(row["measured_at"])
            kg = _number(row["weight_kg"])
            if kg is not None:
                weight.append({"date": day, "weight_lb": round(kg / KG_PER_LB, 2),
                               "method": "scale", "source": "Tracker vitals"})
            sys, dia, pulse = (_number(row[x]) for x in ("systolic", "diastolic", "pulse_bpm"))
            if any(x is not None for x in (sys, dia, pulse)):
                bp.append({"date": day, "systolic_mmHg": sys,
                           "diastolic_mmHg": dia, "pulse_bpm": pulse})
        series = [(date.fromisoformat(x["date"]), x["weight_lb"]) for x in weight]
        weekly = {}
        monthly = {}
        for name, n in (("7d", 7), ("28d", 28)):
            recent = [v for d, v in series if d >= on - timedelta(days=n-1)]
            weekly[name] = _average(recent)
        for name, n in (("7d", 7), ("28d", 28)):
            eligible = [x for x in series if x[0] >= on - timedelta(days=n-1)]
            monthly[name] = round(eligible[-1][1] - eligible[0][1], 2) if len(eligible) >= 2 else None
        oldest = first[0] if first else None
        initial_lb = _number(oldest["weight_kg"]) / KG_PER_LB if oldest and _number(oldest["weight_kg"]) is not None else None
        body = {"waist_history": [], "other_circumferences": [],
                "waist_to_height_ratio": None, "body_fat_estimates": [],
                "status": "not_recorded_in_current_tracker_schema"}
        # Only completed sessions count toward strength and frequency.
        sessions = _select(db, "workout_sessions654", """
            SELECT id, started_at, completed_at FROM workout_sessions654
            WHERE substr(started_at,1,10) BETWEEN ? AND ?
            ORDER BY started_at
        """, (period["from"], period["to"]))
        equipment = {x["id"]: x for x in _select(db, "workout_equipment654", """
            SELECT id, name, kind, manufacturer, model FROM workout_equipment654
        """)}
        types = {}
        if "workout_set_types667" in table_names:
            types = {x["set_id"]: x["set_type"] for x in _select(db, "workout_set_types667",
                "SELECT set_id, set_type FROM workout_set_types667")}
        sets = _select(db, "workout_sets654", """
            SELECT id, session_id, equipment_id, weight_lb, reps, performed_at
            FROM workout_sets654 WHERE session_id IN (
                SELECT id FROM workout_sessions654
                WHERE substr(started_at,1,10) BETWEEN ? AND ?)
            ORDER BY performed_at, id
        """, (period["from"], period["to"]))
        by_session = defaultdict(list)
        best = {}
        by_machine = defaultdict(lambda: {"sets": 0, "volume_lb_reps": 0})
        for s in sets:
            equip = equipment.get(s["equipment_id"])
            if equip is None:
                continue
            row = {"equipment_id": s["equipment_id"], "exercise": equip["name"],
                   "kind": equip["kind"], "weight_lb": _number(s["weight_lb"]),
                   "repetitions": s["reps"], "set_type": types.get(s["id"], "working")}
            by_session[s["session_id"]].append(row)
        workout_rows = []
        completed_days = set()
        for s in sessions:
            work = by_session.get(s["id"], [])
            done = s["completed_at"] is not None
            session_day = _date(s["started_at"])
            if done and work:
                completed_days.add(session_day)
                for x in work:
                    if x["set_type"] != "working" or x["weight_lb"] is None:
                        continue
                    key = str(x["equipment_id"])
                    group = by_machine[key]
                    group["sets"] += 1
                    group["volume_lb_reps"] += x["weight_lb"] * x["repetitions"]
                    old = best.get(key)
                    if old is None or (x["weight_lb"], x["repetitions"]) > (
                            old["weight_lb"], old["repetitions"]):
                        best[key] = {"equipment_id": x["equipment_id"],
                                     "exercise": x["exercise"],
                                     "weight_lb": x["weight_lb"],
                                     "repetitions": x["repetitions"],
                                     "date": session_day}
            workout_rows.append({"date": session_day,
                                  "status": "completed" if done else "in_progress",
                                  "sets": work})
        # Food data are explicit journal nutrient values multiplied by servings.
        foods = _select(db, "tracker_food_entries", """
            SELECT e.eaten_on, e.servings, p.nutrients
            FROM tracker_food_entries e JOIN tracker_food_products p
            ON e.product_id=p.id WHERE e.eaten_on BETWEEN ? AND ?
            ORDER BY e.eaten_on
        """, (period["from"], period["to"]))
        nutrition_by_day = defaultdict(list)
        for f in foods:
            try:
                packed = json.loads(f["nutrients"])
            except (TypeError, ValueError):
                packed = {}
            servings = _number(f["servings"])
            if not isinstance(packed, dict) or servings is None or servings < 0:
                continue
            nutrition_by_day[f["eaten_on"]].append((servings, packed))
        targets = {x["nutrient"]: _number(x["value"]) for x in _select(db, "tracker_food_targets",
            "SELECT nutrient, value FROM tracker_food_targets WHERE nutrient IN ('energy','proteins','carbohydrates','fat')")}
        nutrition_rows = []
        for offset in range(days):
            stamp = (start + timedelta(days=offset)).isoformat()
            entries = nutrition_by_day.get(stamp, [])
            totals = {}
            reported = {}
            for key in NUTRIENTS:
                values = [servings * _number(values[key]) for servings, values in entries
                          if _number(values.get(key)) is not None]
                totals[key] = round(sum(values), 2) if values else None
                reported[key] = len(values)
            nutrition_rows.append({
                "date": stamp, "logged_foods": len(entries),
                "totals": totals, "reported_foods": reported,
                "complete": bool(entries) and all(reported[x] == len(entries) for x in NUTRIENTS),
                "protein_target_met": (
                    totals["proteins"] >= targets["proteins"]
                    if totals["proteins"] is not None and targets.get("proteins") is not None
                    else None),
            })
        lab_names = {str(x).strip().casefold() for x in lab_allowlist if str(x).strip()}
        if len(lab_names) > 40:
            raise ValueError("Lab allowlist too large")
        lab_rows = []
        if lab_names and {"lab_results", "lab_reports"} <= table_names:
            found = db.execute("""
                SELECT r.drawn_on, a.analyte, a.value, a.unit,
                       a.ref_low, a.ref_high
                FROM lab_results a JOIN lab_reports r ON r.id = a.report_id
                WHERE r.drawn_on BETWEEN ? AND ? ORDER BY r.drawn_on
            """, (period["from"], period["to"]))
            for row in found:
                if str(row["analyte"]).strip().casefold() not in lab_names:
                    continue
                num = _number(row["value"])
                if num is None:
                    continue
                lab_rows.append({"date": _date(row["drawn_on"]), "analyte": row["analyte"],
                                 "value": num, "unit": row["unit"],
                                 "reference_low": _number(row["ref_low"]),
                                 "reference_high": _number(row["ref_high"])})
        medications = {str(x).strip().casefold() for x in medication_allowlist if str(x).strip()}
        if len(medications) > 30:
            raise ValueError("Medication allowlist too large")
        intervention_rows = []
        if medications and {"regimen_items635", "regimen_schedules635"} <= table_names:
            regimens = db.execute("""
                SELECT i.kind, i.name, s.start_on, s.end_on, s.amount, s.cadence
                FROM regimen_schedules635 s JOIN regimen_items635 i ON i.id=s.item_id
                WHERE s.start_on <= ? AND (s.end_on IS NULL OR s.end_on >= ?)
                ORDER BY s.start_on
            """, (period["to"], period["from"]))
            for x in regimens:
                if x["kind"] != "medication" or x["name"].strip().casefold() not in medications:
                    continue
                intervention_rows.append({
                    "date": _date(x["start_on"]), "type": "recorded_schedule",
                    "medication": x["name"], "planned_amount": x["amount"],
                    "cadence": x["cadence"], "end_date": _date(x["end_on"]),
                    "certainty": "recorded_plan_not_confirmed_administration",
                })
        db.execute("ROLLBACK")
    finally:
        db.close()
    summary = {
        "starting_weight": {"date": _date(oldest["measured_at"]),
                            "weight_lb": round(initial_lb, 2)} if initial_lb is not None else None,
        "current_weight_lb": weight[-1]["weight_lb"] if weight else None,
        "goal_weight_lb": None,
        "moving_average_lb": weekly,
        "change_lb": monthly,
        "method": "observed_scale_weight_only",
    }
    workouts = {
        "sessions": workout_rows, "completed_training_days": len(completed_days),
        "weekly_frequency_7d": sum(1 for r in workout_rows if r["status"]=="completed" and
                                   r["sets"] and r["date"] >= (on-timedelta(days=6)).isoformat()),
        "machine_progress": [{
            "equipment_id": int(k), "working_sets": v["sets"],
            "volume_lb_reps": round(v["volume_lb_reps"], 2),
            "best_load": best.get(k)} for k, v in sorted(by_machine.items())],
        "comparison_rule": "same_equipment_id_only",
    }
    active_logged = [x for x in nutrition_rows if x["logged_foods"]]
    nutrition = {
        "daily": nutrition_rows,
        "targets": {"protein_g": targets.get("proteins")},
        "logged_days": len(active_logged),
        "complete_days": sum(x["complete"] for x in active_logged),
        "average_on_logged_days": {
            k: _average([x["totals"][k] for x in active_logged
                         if x["totals"][k] is not None]) for k in NUTRIENTS},
        "missing_day_policy": "null_not_zero",
    }
    categories = {
        "weight": {"summary": summary, "history": weight},
        "body-measurements": body,
        "workouts": workouts, "nutrition": nutrition,
        "vitals": {"history": bp, "unit": {"bp": "mmHg", "pulse": "bpm"}},
        "labs": {"history": lab_rows, "allowlist_applied": True},
        "interventions": {"history": intervention_rows, "allowlist_applied": True},
        "overview": {"weight_current_lb": summary["current_weight_lb"],
                     "weight_change_28d_lb": monthly["28d"],
                     "completed_workouts": sum(x["status"]=="completed" for x in workout_rows),
                     "food_logging_days": len(active_logged),
                     "unavailable": ["waist_history", "body_fat_history", "goal_weight"]},
    }
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
    output = {}
    for name in CATEGORIES:
        values = categories[name]
        count = (len(values["history"]) if name in ("weight", "vitals", "labs", "interventions")
                 else len(values["sessions"]) if name == "workouts"
                 else values["logged_days"] if name == "nutrition" else None)
        output[name] = {
            "schema_version": SCHEMA_VERSION, "source_instance": instance,
            "generated_at_utc": now, "reporting_period": period,
            "classification": "observed_and_descriptive_calculations",
            "completeness": {
                "observed_records": count, "reporting_days": days,
                "measurement_available": (
                    False if name == "body-measurements" else
                    bool(count) if count is not None else True),
            },
            "provenance": {
                "history": "directly_recorded_where_present",
                "summaries": "calculated_from_records",
                "body_composition": "not_estimated",
            },
            "data": values,
        }
    return output


def canonical(payload):
    return json.dumps(payload, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def semantic_digest(datasets):
    content = {k: {a: b for a, b in v.items() if a != "generated_at_utc"}
               for k, v in datasets.items()}
    return hashlib.sha256(canonical(content)).hexdigest()
