"""Read-only, measurement-aware reconstitution arithmetic.

The output is a nominal volume calculation, not a preparation
or administration recommendation.
"""

from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP

from . import units as U


def positive(raw, label):
    try:
        value = Decimal(str(raw))
    except (ArithmeticError, ValueError, TypeError):
        raise ValueError(f"{label} must be a number.")

    if (
        not value.is_finite()
        or value <= 0
        or value > Decimal("1e9")
    ):
        raise ValueError(
            f"{label} must be finite, positive and "
            "within supported limits."
        )

    return value


def optimize_reconstitution(payload):
    """Calculate nominal dilution options without changing inventory."""

    if not isinstance(payload, dict):
        raise ValueError("Invalid calculator input.")

    if payload.get("kind", "single") != "single":
        raise ValueError(
            "Use single compound mode for this calculator."
        )

    sources = payload.get("components")

    if (
        not isinstance(sources, list)
        or len(sources) != 1
        or not isinstance(sources[0], dict)
    ):
        raise ValueError("Enter exactly one compound.")

    source = sources[0]

    content_unit = U.parse_unit(
        str(source.get("unit", "mg"))
    )
    target_unit = U.parse_unit(
        str(payload.get("target_unit", "mcg"))
    )

    if (
        content_unit.dim not in ("mass", "iu")
        or target_unit.dim != content_unit.dim
    ):
        raise ValueError(
            "Vial content and target require compatible units."
        )

    name = str(
        source.get("name") or "Compound"
    ).strip()[:120]

    vial_content = positive(
        source.get("amount"), "Vial contents"
    )
    target_amount = positive(
        payload.get("target_amount"),
        "Entered amount per draw",
    )

    content_base = (
        vial_content * Decimal(str(content_unit.factor))
    )
    target_base = (
        target_amount * Decimal(str(target_unit.factor))
    )

    if target_base > content_base:
        raise ValueError(
            "Entered amount exceeds the entire vial contents."
        )

    ratio = content_base / target_base

    if ratio > Decimal("1000000"):
        raise ValueError(
            "Entered amount is too small relative to vial contents."
        )

    count = int(
        ratio.to_integral_value(rounding=ROUND_FLOOR)
    )

    leftover_base = (
        content_base - target_base * count
    )

    if leftover_base < 0:
        leftover_base = Decimal(0)

    raw_capacity = payload.get("vial_capacity_ml")
    capacity = positive(
        "3" if raw_capacity in (None, "") else raw_capacity,
        "Assumed vial capacity",
    )

    syringe = positive(
        payload.get("syringe_ml", 1),
        "Syringe capacity",
    )

    if syringe not in (
        Decimal("0.3"),
        Decimal("0.5"),
        Decimal("1"),
    ):
        raise ValueError(
            "Choose a 0.3, 0.5 or 1 mL U-100 syringe."
        )

    preferred = positive(
        payload.get("preferred_units", 10),
        "Preferred U-100 marks",
    )

    if preferred > syringe * 100:
        raise ValueError(
            "Preferred marks exceed the selected syringe capacity."
        )

    increment = positive(
        payload.get("graduation_units", 1),
        "Syringe mark increment",
    )

    if increment not in (
        Decimal("0.5"),
        Decimal("1"),
        Decimal("2"),
    ):
        raise ValueError(
            "Choose a 0.5, 1 or 2 unit mark increment."
        )

    step = positive(
        payload.get("volume_step_ml", "0.01"),
        "Final-volume measurement increment",
    )

    if step not in (
        Decimal("0.01"),
        Decimal("0.05"),
        Decimal("0.1"),
    ):
        raise ValueError(
            "Choose a supported final-volume increment."
        )

    if capacity > Decimal("1000"):
        raise ValueError(
            "Vial capacity exceeds supported limits."
        )

    candidates = []

    possible_marks = int(
        (
            syringe * Decimal(100) / increment
        ).to_integral_value(rounding=ROUND_FLOOR)
    )

    for index in range(1, possible_marks + 1):
        marks = increment * index
        draw_ml = marks / Decimal(100)

        # Total vial contents / entered amount gives
        # the theoretical number of complete and partial draws.
        nominal_final = ratio * draw_ml

        if nominal_final > capacity or nominal_final > 1000:
            continue

        rounded_steps = (
            nominal_final / step
        ).to_integral_value(rounding=ROUND_HALF_UP)

        rounded_ml = rounded_steps * step

        # Do not silently use a rounded liquid volume
        # as though it produces the identical concentration.
        exact_grid = rounded_ml == nominal_final

        error_pct = None

        if rounded_ml > 0:
            delivered_base = (
                content_base * draw_ml / rounded_ml
            )

            error_pct = (
                delivered_base / target_base - 1
            ) * 100

        leftover_ml = (
            nominal_final * leftover_base / content_base
        )

        candidates.append({
            "draw_units": float(marks),
            "draw_ml": float(draw_ml),
            "nominal_final_ml": float(nominal_final),
            "matches_volume_step": exact_grid,
            "nearest_measurable_ml": float(rounded_ml),
            "rounding_error_pct": (
                float(error_pct)
                if error_pct is not None else None
            ),
            "theoretical_leftover_ml": float(leftover_ml),
            "_rank": (
                0 if exact_grid else 1,
                abs(marks - preferred),
                abs(nominal_final - rounded_ml),
                nominal_final,
            ),
        })

    if not candidates:
        raise ValueError(
            "No selected syringe-mark increment fits the "
            "assumed vial capacity. Change the vial capacity "
            "or graduation setting; do not assume sub-mark "
            "measurements are possible."
        )

    # Prefer a final volume that can be measured exactly
    # on the selected nominal volume grid, then a draw
    # near the user's preferred marking.
    candidates.sort(key=lambda item: item["_rank"])

    options = candidates[:5]

    for item in options:
        item.pop("_rank")

    best = options[0]

    warnings = [
        "Final volumes are nominal, not verified amounts "
        "of water to add. Powder displacement, solubility "
        "and vial headspace have not been measured.",

        "Theoretical remainder excludes syringe dead space, "
        "vial hold-up and transfer losses. Dilution cannot "
        "guarantee zero physical waste.",
    ]

    if not best["matches_volume_step"]:
        warnings.append(
            "No exact option aligns with the selected volume "
            "measurement increment. Rounding the final volume "
            "changes the concentration and delivered amount."
        )

    if best["draw_units"] < 5:
        warnings.append(
            "Selected draw is below 5 U-100 marks. Confirm "
            "the actual syringe supports this small volume."
        )

    if leftover_base > 0:
        warnings.append(
            "Vial contents are not an exact multiple of the "
            "entered amount. The remaining fraction cannot "
            "produce another complete draw."
        )

    return {
        "method": "optimize",
        "kind": "single",
        "compound": name,
        "content": float(vial_content),
        "content_unit": content_unit.name,
        "target_amount": float(target_amount),
        "target_unit": target_unit.name,
        "complete_draws": count,
        "theoretical_leftover": float(
            leftover_base / Decimal(str(content_unit.factor))
        ),
        "remaining_fraction_pct": float(
            leftover_base / content_base * 100
        ),
        "syringe_ml": float(syringe),
        "assumed_vial_capacity_ml": float(capacity),
        "capacity_is_default": raw_capacity in (None, ""),
        "graduation_units": float(increment),
        "preferred_units": float(preferred),
        "volume_step_ml": float(step),
        "recommended": best,
        "options": options,
        "warnings": warnings,
    }
