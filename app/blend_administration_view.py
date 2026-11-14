"""Read-only projection of blend draws into administration views.

A BlendDose is one physical draw, not a DoseLog from each constituent vial.
Display constituent contributions without creating duplicate inventory writes.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import units as U
from .models import BlendDose, Blend, BlendComponent


def blend_dose_components(draw: BlendDose) -> list[dict]:
    """Amounts from recorded transfer ratios, in native base units.

    Deduplicate constituent compound IDs, because one physical draw can
    include multiple transfers of the same compound.
    """
    amounts: dict[int, dict] = {}
    blend = draw.blend
    if blend.final_volume_ml <= 0:
        return []
    for component in blend.components:
        if component.compound is None or component.source_vial is None:
            continue
        dim = U.parse_unit(component.source_vial.content_unit).dim
        unit = U.BASE_UNIT[dim]
        value = draw.volume_ml * component.transferred_base / blend.final_volume_ml
        row = amounts.setdefault(component.compound_id, {
            "compound_id": component.compound_id,
            "name": component.compound.name,
            "amount": 0.0,
            "unit": unit,
        })
        if row["unit"] != unit:
            # Never merge physically incompatible units.
            continue
        row["amount"] += value
    return list(amounts.values())


def blend_history(db: Session, compound_id: int | None = None,
                  limit: int = 60) -> list[dict]:
    """Recent physical draws, filtered by constituent when requested."""
    draws = list(db.scalars(
        select(BlendDose)
        .options(
            selectinload(BlendDose.blend)
            .selectinload(Blend.components)
            .selectinload(BlendComponent.compound),
            selectinload(BlendDose.blend)
            .selectinload(Blend.components)
            .selectinload(BlendComponent.source_vial),
        )
        .order_by(BlendDose.taken_at.desc(), BlendDose.id.desc())
    ))
    rows = []
    for draw in draws:
        components = blend_dose_components(draw)
        if compound_id is not None and not any(
            item["compound_id"] == compound_id for item in components
        ):
            continue
        rows.append({"draw": draw, "blend": draw.blend,
                     "components": components})
        if len(rows) >= limit:
            break
    return rows
