"""Per-serving macro previews for Tracker Food Journal."""

import json
import math

MACROS = (
    ("energy", "Cal"),
    ("proteins", "P"),
    ("carbohydrates", "C"),
    ("fat", "F"),
)


def per_serving(raw):
    """Keep missing and invalid nutrient values distinct from zero."""
    try:
        values = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        values = {}

    if not isinstance(values, dict):
        values = {}

    result = {}

    for key, _ in MACROS:
        value = values.get(key)

        if value is None or isinstance(value, bool):
            result[key] = None
            continue

        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            result[key] = None
            continue

        if (
            not math.isfinite(number)
            or number < 0
            or number > 100000
        ):
            result[key] = None
            continue

        result[key] = number

    return result


def attach_previews(rows):
    """Add display-only macro values to existing row dictionaries."""
    for row in rows:
        row["macro_per_serving"] = per_serving(
            row.get("nutrients")
        )
    return rows
