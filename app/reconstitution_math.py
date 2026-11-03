"""Unit-aware single-vial and shared-volume blend arithmetic.

No dosing recommendations, inventory writes or mixing assumptions.
"""

from math import floor, isfinite
from . import units as U


def positive(raw, label):
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{label} must be a number.")

    if not isfinite(value) or value <= 0 or value > 1e9:
        raise ValueError(
            f"{label} must be positive, finite and within supported limits."
        )
    return value


def calculate(payload):
    if not isinstance(payload, dict):
        raise ValueError("Invalid calculator input.")

    if payload.get("method") == "optimize":
        from .reconstitution_optimizer import optimize_reconstitution
        return optimize_reconstitution(payload)

    kind = payload.get("kind", "single")
    method = payload.get("method", "target")

    if kind not in ("single", "blend"):
        raise ValueError("Unknown vial type.")

    if method not in ("target", "draw", "reverse"):
        raise ValueError("Unknown calculation mode.")

    sources = payload.get("components")

    if not isinstance(sources, list) or not 1 <= len(sources) <= 8:
        raise ValueError("Enter between 1 and 8 components.")

    if kind == "single" and len(sources) != 1:
        raise ValueError("A single vial requires one component.")

    if kind == "blend" and len(sources) < 2:
        raise ValueError("A blend requires at least two components.")

    components = []

    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError("Invalid component row.")

        name = str(
            source.get("name") or f"Component {index + 1}"
        ).strip()

        if len(name) > 120:
            raise ValueError("Component name is too long.")

        unit = U.parse_unit(str(source.get("unit", "mg")))

        if unit.dim not in ("mass", "iu"):
            raise ValueError(
                "Components must be expressed in mass or IU."
            )

        amount = positive(
            source.get("amount"), f"{name} vial content"
        )
        base, dim = U.to_base(amount, unit.name)

        if not isfinite(base) or base <= 0:
            raise ValueError("Invalid component content.")

        components.append({
            "name": name,
            "vial_amount": amount,
            "unit": unit.name,
            "base": base,
            "dim": dim,
        })

    syringe_ml = positive(
        payload.get("syringe_ml", 1), "Syringe capacity"
    )

    if syringe_ml not in (0.3, 0.5, 1.0):
        raise ValueError(
            "Choose a 0.3, 0.5 or 1 mL U-100 syringe."
        )

    capacity_raw = payload.get("vial_capacity_ml")
    capacity = (
        positive(capacity_raw, "Vial capacity")
        if capacity_raw not in (None, "")
        else None
    )

    target_basis = payload.get("basis", "0")

    if method != "draw":
        unit = U.parse_unit(
            str(payload.get("target_unit", "mcg"))
        )
        amount = positive(
            payload.get("target_amount"),
            "Entered target amount",
        )
        target, target_dim = U.to_base(
            amount, unit.name
        )

        if target_basis == "total":
            dimensions = {
                component["dim"]
                for component in components
            }

            if (
                len(dimensions) != 1
                or target_dim not in dimensions
            ):
                raise ValueError(
                    "A total blend amount requires compatible "
                    "units for every component."
                )

            reference = sum(
                component["base"]
                for component in components
            )

        else:
            try:
                index = int(target_basis)
            except (TypeError, ValueError, OverflowError):
                raise ValueError("Choose a target component.")

            if (
                str(index) != str(target_basis)
                or not 0 <= index < len(components)
            ):
                raise ValueError("Choose a target component.")

            selected = components[index]

            if target_dim != selected["dim"]:
                raise ValueError(
                    "Entered target unit does not match "
                    "the selected component."
                )

            reference = selected["base"]

        if target > reference * (1 + 1e-10):
            raise ValueError(
                "Entered target exceeds the entire vial content."
            )

        fraction = target / reference

        if not isfinite(fraction) or fraction <= 0:
            raise ValueError("Invalid target fraction.")

    if method == "reverse":
        marks = positive(
            payload.get("draw_units"),
            "Selected U-100 marks",
        )
        draw_ml = marks / 100.0
        volume = draw_ml / fraction

    else:
        volume = positive(
            payload.get("volume_ml"),
            "Nominal final liquid volume",
        )

        if method == "draw":
            marks = positive(
                payload.get("draw_units"),
                "Selected U-100 marks",
            )
            draw_ml = marks / 100.0
        else:
            draw_ml = volume * fraction

    if not isfinite(volume) or not 0 < volume <= 1000:
        raise ValueError(
            "Calculated final liquid volume exceeds "
            "the supported range (0–1000 mL)."
        )

    if not isfinite(draw_ml) or draw_ml <= 0:
        raise ValueError("Calculated draw volume is invalid.")

    if draw_ml > volume * (1 + 1e-10):
        raise ValueError(
            "Selected draw exceeds the entire vial volume."
        )

    units = U.ml_to_syringe_units(draw_ml)
    result_rows = []

    for source in components:
        conc = source["vial_amount"] / volume
        dose = (
            source["vial_amount"]
            * (draw_ml / volume)
        )
        per_mark = (
            source["vial_amount"]
            / (volume * 100)
        )

        if not all(
            isfinite(x)
            for x in (conc, dose, per_mark)
        ):
            raise ValueError(
                "Calculation exceeds numeric limits."
            )

        result_rows.append({
            "name": source["name"],
            "unit": source["unit"],
            "vial_amount": source["vial_amount"],
            "concentration": conc,
            "per_mark": per_mark,
            "amount_per_draw": dose,
        })

    warnings = []

    if draw_ml > syringe_ml + 1e-10:
        warnings.append(
            "Calculated volume exceeds the selected syringe "
            "capacity. This is not an actionable syringe setting."
        )

    if capacity is not None and volume > capacity + 1e-10:
        warnings.append(
            "Nominal final liquid volume exceeds "
            "the entered vial capacity."
        )

    if abs(units - round(units)) > 1e-6:
        warnings.append(
            "The U-100 result falls between whole-unit marks; "
            "check the actual syringe graduations."
        )

    return {
        "kind": kind,
        "method": method,
        "final_volume_ml": volume,
        "draw_ml": draw_ml,
        "draw_units": units,
        "syringe_ml": syringe_ml,
        "fits_syringe": draw_ml <= syringe_ml + 1e-10,
        "full_draws": floor(
            (volume / draw_ml) + 1e-10
        ),
        "components": result_rows,
        "warnings": warnings,
    }
