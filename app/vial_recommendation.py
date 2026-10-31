"""Read-only vial inventory recommendation utilities.

Recommendations are based on recorded inventory and
dates, not clinical suitability or sterility.
"""

from datetime import date, datetime


def as_date(value):
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return None


def first_use_date(vial):
    """Earliest recorded puncture or administration date."""

    values = (
        getattr(vial, "first_punctured_on", None),
        getattr(vial, "first_dosed_on", None),
    )

    dates = [
        as_date(value)
        for value in values
        if as_date(value) is not None
    ]

    return min(dates) if dates else None


def date_warnings(vial, today=None):
    """Return recorded expiration and beyond-use warnings."""

    if today is None:
        today = date.today()

    warnings = []

    expiration = as_date(
        getattr(vial, "expires_on", None)
    )

    beyond_use = as_date(
        getattr(vial, "beyond_use_on", None)
    )

    if expiration is not None and expiration <= today:
        warnings.append("Expiration date reached")

    if beyond_use is not None and beyond_use <= today:
        warnings.append("Beyond-use date reached")

    return warnings


def rank_vials(vials, guidance, today=None):
    """Rank eligible vials using inventory and recorded dates.

    Returns:
        recommended_vial_id, warnings_by_vial_id

    A vial must:
      - Have eligible inventory guidance.
      - Not have reached a recorded expiration date.
      - Not have reached a recorded beyond-use date.

    Among candidates:
      1. Prefer in-use vials.
      2. Prefer known first-use dates.
      3. Prefer earlier first-use dates.
      4. Use vial ID as the final tiebreaker.
    """

    if today is None:
        today = date.today()

    warnings = {}
    candidates = []

    for vial in vials:
        vial_warnings = date_warnings(vial, today)

        warnings[vial.id] = vial_warnings

        if vial_warnings:
            continue

        if not guidance.get(vial.id, {}).get(
            "eligible", False
        ):
            continue

        candidates.append(vial)

    def sort_key(vial):
        first_use = first_use_date(vial)

        return (
            0 if vial.status == "in_use" else 1,
            0 if first_use is not None else 1,
            first_use or date.max,
            vial.id,
        )

    candidates.sort(key=sort_key)

    recommended_id = (
        candidates[0].id
        if candidates
        else None
    )

    return recommended_id, warnings
