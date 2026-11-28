"""Shared validation and descriptive calculations for self-reported outcomes."""
from datetime import date, datetime, timedelta
import json
import math
from statistics import mean

INTENSITY = ("None", "Mild", "Moderate", "Strong", "Intense")
QUALITY = ("Very poor", "Poor", "Fair", "Good", "Excellent")
LEVEL = ("Very low", "Low", "Moderate", "High", "Very high")
METRICS = {
    "hunger": ("Hunger", INTENSITY),
    "food_noise": ("Food noise", INTENSITY),
    "cravings": ("Cravings", INTENSITY),
    "energy": ("Energy", LEVEL),
    "mood": ("Mood", QUALITY),
    "sleep_quality": ("Sleep quality", QUALITY),
    "sleep_duration": ("Sleep duration (hours)", None),
    "libido": ("Libido", LEVEL),
    "erectile_function": ("Erectile function", QUALITY),
    "recovery": ("Physical recovery", QUALITY),
    "muscle_soreness": ("Muscle soreness", INTENSITY),
    "joint_pain": ("Joint pain", INTENSITY),
    "wellbeing": ("General well-being", QUALITY),
    "stress": ("Stress", INTENSITY),
    "motivation": ("Motivation", LEVEL),
}
DEFAULT_METRICS = ("hunger", "food_noise", "energy", "mood", "sleep_quality", "sleep_duration", "recovery", "wellbeing")
SYMPTOMS = ("Nausea", "Constipation", "Diarrhea", "Bloating", "Reflux", "Headache",
            "Fatigue", "Dizziness", "Fluid retention", "Muscle soreness",
            "Joint pain", "Sleep disturbance", "Other")
REACTIONS = ("Soreness", "Redness", "Swelling", "Bruising", "Itching", "Firmness or lump", "Other", "No reaction reported")

def metric_order(values):
    values = tuple(values)
    if len(values) != len(set(values)) or any(v not in METRICS for v in values):
        raise ValueError("Choose distinct supported wellness metrics.")
    return values

def saved_order(setting):
    return metric_order(json.loads(setting.metrics_json)) if setting else DEFAULT_METRICS

def checked_day(raw, today=None):
    today = today or date.today()
    try:
        value = date.fromisoformat(str(raw))
    except (TypeError, ValueError):
        raise ValueError("Choose a valid date.") from None
    if not date(1900, 1, 1) <= value <= today:
        raise ValueError("Date is outside the supported range.")
    return value

def checked_time(raw, *, now=None):
    try:
        value = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        raise ValueError("Choose a valid date and time.") from None
    if value.tzinfo is not None or not datetime(1900, 1, 1) <= value <= (now or datetime.now()):
        raise ValueError("Date and time must be local and not in the future.")
    return value

def checked_notes(raw):
    value = str(raw or "").strip()
    if len(value) > 2000 or any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ValueError("Notes must be at most 2000 characters.")
    return value

def metric_values(form, keys):
    result = {}
    for key in metric_order(keys):
        raw = str(form.get(key, "")).strip()
        if not raw:
            continue
        try:
            value = float(raw)
        except (ValueError, OverflowError):
            raise ValueError("Invalid wellness rating.") from None
        if not math.isfinite(value):
            raise ValueError("Invalid wellness rating.")
        if key == "sleep_duration":
            if not 0 <= value <= 24:
                raise ValueError("Sleep duration must be between 0 and 24 hours.")
        else:
            if value not in (1, 2, 3, 4, 5):
                raise ValueError("Choose a rating from 1 to 5.")
            value = int(value)
        result[key] = value
    return result

def episode_values(form, types, *, allow_absent=False):
    kind = str(form.get("kind", ""))
    if kind not in types:
        raise ValueError("Choose a supported type.")
    severity = str(form.get("severity", ""))
    absent = allow_absent and kind == "No reaction reported"
    if severity not in (("0",) if absent else ("1", "2", "3", "4", "5")):
        raise ValueError("Choose an appropriate severity.")
    onset = checked_time(form.get("onset_at"))
    resolved = checked_time(form.get("resolved_at")) if form.get("resolved_at") else None
    if resolved and resolved < onset:
        raise ValueError("Resolution cannot precede onset.")
    return dict(severity=int(severity), onset_at=onset, resolved_at=resolved, notes=checked_notes(form.get("notes")))

def metric_summary(rows):
    samples = {k: [] for k in METRICS}
    for row in rows:
        for key, value in json.loads(row.values_json).items():
            if key in samples and isinstance(value, (int,float)) and math.isfinite(value):
                samples[key].append(value)
    return {key: {"count": len(values), "average": round(mean(values), 2) if values else None}
            for key, values in samples.items()}
