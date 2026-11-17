"""Release 668 strict CSV plan exchange.

A CSV import changes future routine targets only. Rows use routine item IDs,
never display names, to avoid ambiguous machine matching. Validate the entire
document before changing any ORM objects. Historical session targets and sets
are untouched.
"""
from __future__ import annotations

import csv
from io import StringIO

from .workout_program667 import parse_goal667, rest667

FIELDS668 = ("routine_item_id", "sets", "reps", "weight_lb", "rest_seconds", "setup_note")
MAX_CSV_BYTES668 = 32768
MAX_CSV_ROWS668 = 30


def parse_routine_csv668(payload: str, allowed_item_ids: set[int]) -> list[dict]:
    if not payload or len(payload.encode("utf-8")) > MAX_CSV_BYTES668:
        raise ValueError("CSV must contain at most 32 KiB of text.")
    try:
        reader = csv.DictReader(StringIO(payload.lstrip("\ufeff"), newline=""), strict=True)
        if reader.fieldnames != list(FIELDS668):
            raise ValueError("CSV columns do not match the supported routine-plan format.")
        parsed = []
        seen: set[int] = set()
        for index, row in enumerate(reader, 2):
            if index > MAX_CSV_ROWS668 + 1:
                raise ValueError("A routine CSV may contain at most 30 exercises.")
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"CSV row {index} has missing or extra columns.")
            key = row["routine_item_id"].strip()
            if not key.isascii() or not key.isdecimal():
                raise ValueError(f"CSV row {index} has an invalid routine item ID.")
            item_id = int(key)
            if item_id not in allowed_item_ids or item_id in seen:
                raise ValueError(f"CSV row {index} references an unknown or repeated exercise.")
            seen.add(item_id)
            goal = parse_goal667(row["sets"], row["reps"], row["weight_lb"])
            rest = rest667(row["rest_seconds"], optional=True)
            note = row["setup_note"].strip()
            if len(note) > 1000:
                raise ValueError(f"CSV row {index} has setup notes longer than 1,000 characters.")
            parsed.append(dict(
                routine_item_id=item_id, target_sets=goal[0], target_reps=goal[1],
                target_weight_lb=goal[2], rest_seconds=rest, setup_note=note,
            ))
        if not parsed:
            raise ValueError("CSV has no exercise rows.")
        return parsed
    except (csv.Error, UnicodeError) as exc:
        raise ValueError("Malformed routine CSV.") from exc


def csv_cell668(value: object) -> str:
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")) or (text and text[0].isspace()):
        return "'" + text
    return text


def render_routine_csv668(rows: list[dict]) -> str:
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(FIELDS668)
    for row in rows:
        writer.writerow([csv_cell668(row.get(key)) for key in FIELDS668])
    return output.getvalue()


HISTORICAL_FIELDS668 = (
    "equipment_id", "weight_lb", "reps", "effort", "set_time",
)


def parse_historical_csv668(payload: str) -> list[dict[str, str]]:
    """Parse only CSV structure; Release 658 validates actual values/window."""
    if not payload or len(payload.encode("utf-8")) > MAX_CSV_BYTES668:
        raise ValueError("Historical CSV must contain at most 32 KiB.")
    try:
        reader = csv.DictReader(StringIO(payload.lstrip("\ufeff"), newline=""), strict=True)
        if reader.fieldnames != list(HISTORICAL_FIELDS668):
            raise ValueError("Historical CSV columns must be equipment_id,weight_lb,reps,effort,set_time.")
        result = []
        for number, row in enumerate(reader, 2):
            if number > 41:
                raise ValueError("Historical CSV may contain at most 40 recorded sets.")
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"Historical CSV row {number} has incomplete or extra fields.")
            result.append({key: str(row[key]).strip() for key in HISTORICAL_FIELDS668})
        if not result:
            raise ValueError("Historical CSV must contain actual set rows.")
        return result
    except (csv.Error, UnicodeError) as exc:
        raise ValueError("Malformed historical workout CSV.") from exc
