"""Release 755: opt-in, narrowly selected clinical progress history.

The caller already owns a read-only transaction. No table or ORM serialization:
only named, reviewed SQLite columns may leave the database. Never export
attachments, notes, prescribers, purchase/vendor records or vial IDs.
"""
from __future__ import annotations

from datetime import date
import math

MAX_ROWS = 25000
NAME_LIMIT = 160

def clean_text(value, limit=NAME_LIMIT):
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > limit or any(ord(c) < 32 or ord(c) == 127 for c in value):
        return None
    return value

def finite_number(value):
    try:
        if value is None:
            return None
        f = float(value)
        return round(f, 4) if math.isfinite(f) else None
    except (ValueError, TypeError, OverflowError):
        return None

def checked(rows):
    if len(rows) > MAX_ROWS:
        raise ValueError("CLINICAL_EXPORT_TOO_LARGE")
    return rows

def extract_labs755(db, tables: set[str], start: date, end: date):
    if not {"lab_reports", "lab_results"}.issubset(tables):
        return []
    rows = checked(db.execute("""
        SELECT r.drawn_on, a.analyte, a.value, a.unit, a.ref_low, a.ref_high
        FROM lab_results a
        JOIN lab_reports r ON r.id=a.report_id
        WHERE r.drawn_on BETWEEN ? AND ?
        ORDER BY r.drawn_on, a.analyte, a.id
    """, (start.isoformat(), end.isoformat())).fetchall())
    out = []
    for row in rows:
        analyte = clean_text(row["analyte"], 120)
        unit = clean_text(row["unit"], 30)
        value = finite_number(row["value"])
        # A legitimate unitless ratio is still a numeric lab observation.
        if analyte and value is not None:
            out.append({
                "date": str(row["drawn_on"])[:10],
                "analyte": analyte, "value": value, "unit": unit,
                "reference_low": finite_number(row["ref_low"]),
                "reference_high": finite_number(row["ref_high"]),
            })
    return out

def extract_regimens755(db, tables: set[str], start: date, end: date):
    """All medication/supplement schedules and taken/skipped entries.

    Schedule != administration. Item status does not convert a plan to a
    confirmed dose; earlier inactive items remain in historical records.
    """
    if "regimen_items635" not in tables:
        return []
    rows = []
    if "regimen_schedules635" in tables:
        tablet_join = ("LEFT JOIN regimen_tablet_schedule731 ts ON ts.schedule_id=s.id"
                       if "regimen_tablet_schedule731" in tables else "")
        tablet_fields = ("""
            ts.tablet_strength_mg AS tablet_strength_mg,
            ts.prescribed_dose_mg AS prescribed_dose_mg,
            ts.tablets_planned AS tablets_planned
        """ if tablet_join else
            "NULL AS tablet_strength_mg, NULL AS prescribed_dose_mg, NULL AS tablets_planned")
        sql = f"""
            SELECT i.kind, i.name, i.ingredient, i.strength, i.form,
                   i.active AS item_active, s.start_on, s.end_on,
                   s.active AS schedule_active,
                   s.amount, s.cadence, s.weekdays, s.interval_days,
                   s.at_time, {tablet_fields}
            FROM regimen_schedules635 s
            JOIN regimen_items635 i ON i.id=s.item_id
            {tablet_join}
            WHERE s.start_on <= ? AND (s.end_on IS NULL OR s.end_on >= ?)
            ORDER BY s.start_on, s.id
        """
        raw = checked(db.execute(sql, (end.isoformat(), start.isoformat())).fetchall())
        for x in raw:
            if x["kind"] not in ("medication", "supplement"):
                continue
            name = clean_text(x["name"])
            if not name:
                continue
            item = {
                "date": str(x["start_on"])[:10],
                "type": "recorded_schedule",
                "category": x["kind"],
                "name": name,
                "ingredient": clean_text(x["ingredient"]),
                "strength": clean_text(x["strength"], 80),
                "form": clean_text(x["form"], 60),
                "planned_amount": clean_text(x["amount"], 80),
                "cadence": clean_text(x["cadence"], 20),
                "weekdays": clean_text(x["weekdays"], 20),
                "interval_days": x["interval_days"],
                "scheduled_time": clean_text(x["at_time"], 5),
                "end_date": str(x["end_on"])[:10] if x["end_on"] else None,
                "active_item": bool(x["item_active"]),
                "active_schedule": bool(x["schedule_active"]),
                "tablet_strength_mg": finite_number(x["tablet_strength_mg"]),
                "prescribed_dose_mg": finite_number(x["prescribed_dose_mg"]),
                "tablets_planned": finite_number(x["tablets_planned"]),
                "certainty": "recorded_plan_not_confirmed_administration",
            }
            rows.append(item)
    if "regimen_entries635" in tables:
        tablet_join = ("LEFT JOIN regimen_tablet_entry731 te ON te.entry_id=e.id"
                       if "regimen_tablet_entry731" in tables else "")
        tablet_fields = ("""
            te.tablet_strength_mg AS tablet_strength_mg,
            te.administered_dose_mg AS administered_dose_mg,
            te.tablets_taken AS tablets_taken
        """ if tablet_join else
            "NULL AS tablet_strength_mg, NULL AS administered_dose_mg, NULL AS tablets_taken")
        sql = f"""
            SELECT e.logged_at, e.outcome, e.amount,
                   i.kind, i.name, i.ingredient, i.strength, i.form,
                   {tablet_fields}
            FROM regimen_entries635 e
            JOIN regimen_items635 i ON i.id=e.item_id
            {tablet_join}
            WHERE substr(e.logged_at, 1, 10) BETWEEN ? AND ?
            ORDER BY e.logged_at, e.id
        """
        raw = checked(db.execute(sql, (start.isoformat(), end.isoformat())).fetchall())
        for x in raw:
            if x["kind"] not in ("medication", "supplement") or x["outcome"] not in ("taken", "skipped"):
                continue
            name = clean_text(x["name"])
            if not name:
                continue
            rows.append({
                "date": str(x["logged_at"])[:10], "type": "regimen_log",
                "category": x["kind"], "name": name,
                "ingredient": clean_text(x["ingredient"]),
                "strength": clean_text(x["strength"], 80),
                "form": clean_text(x["form"], 60),
                "outcome": x["outcome"],
                "recorded_amount": clean_text(x["amount"], 80),
                "tablet_strength_mg": finite_number(x["tablet_strength_mg"]),
                "administered_dose_mg": finite_number(x["administered_dose_mg"]),
                "tablets_taken": finite_number(x["tablets_taken"]),
                "certainty": "recorded_administration_or_skip",
            })
    return rows

def extract_compounds755(db, tables: set[str], start: date, end: date):
    """Recorded vial/blend administrations and active *planned* protocols."""
    rows = []
    if {"dose_logs", "vials", "compounds"}.issubset(tables):
        raw = checked(db.execute("""
            SELECT d.taken_at, d.entered_value, d.entered_unit,
                   d.amount_base, c.name, c.category, c.primary_unit
            FROM dose_logs d
            JOIN vials v ON v.id=d.vial_id
            JOIN compounds c ON c.id=v.compound_id
            WHERE d.kind='dose'
              AND substr(d.taken_at,1,10) BETWEEN ? AND ?
            ORDER BY d.taken_at, d.id
        """, (start.isoformat(), end.isoformat())).fetchall())
        for x in raw:
            name = clean_text(x["name"])
            amount = finite_number(x["entered_value"])
            unit = clean_text(x["entered_unit"], 8)
            if not (name and amount is not None and unit):
                continue
            # Base quantity is tracked in mcg for mass-based compounds or IU.
            # It is not inferred from syringe units; only stored source value.
            base = finite_number(x["amount_base"])
            rows.append({
                "date": str(x["taken_at"])[:10],
                "type": "recorded_compound_dose",
                "category": clean_text(x["category"], 30),
                "name": name, "recorded_amount": amount,
                "recorded_unit": unit, "tracked_base_amount": base,
                "tracked_base_unit": "IU" if x["primary_unit"]=="IU" else "mcg",
                "certainty": "recorded_administration",
            })
    if {"blend_doses", "blend_components", "compounds"}.issubset(tables):
        ingredients = {}
        for x in checked(db.execute("""
            SELECT DISTINCT b.blend_id, c.name
            FROM blend_components b
            JOIN compounds c ON c.id=b.compound_id
            ORDER BY b.blend_id, c.name
        """).fetchall()):
            name = clean_text(x["name"])
            if name:
                ingredients.setdefault(x["blend_id"], []).append(name)
        raw = checked(db.execute("""
            SELECT blend_id, taken_at, entered_value, entered_unit, volume_ml
            FROM blend_doses
            WHERE kind='dose' AND substr(taken_at,1,10) BETWEEN ? AND ?
            ORDER BY taken_at, id
        """, (start.isoformat(), end.isoformat())).fetchall())
        for x in raw:
            names = ingredients.get(x["blend_id"], [])
            if not names:
                continue
            rows.append({
                "date": str(x["taken_at"])[:10],
                "type": "recorded_blend_dose",
                "category": "compound_blend",
                "compounds": names,
                "recorded_amount": finite_number(x["entered_value"]),
                "recorded_unit": clean_text(x["entered_unit"], 8),
                "withdrawn_volume_ml": finite_number(x["volume_ml"]),
                "certainty": "recorded_blend_administration",
            })
    if {"protocols", "protocol_items", "compounds"}.issubset(tables):
        raw = checked(db.execute("""
            SELECT p.start_date, p.end_date, i.amount_value, i.amount_unit,
                   i.freq_count, i.freq_period, i.start_week, i.end_week,
                   i.dose_days, i.dose_time, c.name, c.category
            FROM protocol_items i
            JOIN protocols p ON p.id=i.protocol_id
            JOIN compounds c ON c.id=i.compound_id
            WHERE p.is_active=1
            ORDER BY p.id, i.position, i.id
        """).fetchall())
        for x in raw:
            name = clean_text(x["name"])
            if not name:
                continue
            rows.append({
                "date": str(x["start_date"])[:10] if x["start_date"] else None,
                "type": "active_protocol_plan",
                "category": clean_text(x["category"], 30),
                "name": name,
                "planned_amount": finite_number(x["amount_value"]),
                "planned_unit": clean_text(x["amount_unit"], 8),
                "frequency_count": finite_number(x["freq_count"]),
                "frequency_period": clean_text(x["freq_period"], 10),
                "start_week": x["start_week"],
                "end_week": x["end_week"],
                "dose_days": clean_text(x["dose_days"], 30),
                "dose_time": clean_text(x["dose_time"], 5),
                "end_date": str(x["end_date"])[:10] if x["end_date"] else None,
                "certainty": "active_what_if_plan_not_confirmed_administration",
            })
    return rows
