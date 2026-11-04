"""Bounded and atomic hypothetical scenario import."""
from datetime import datetime
from fastapi import HTTPException
from pydantic import BaseModel,Field,model_validator

from .models import (
    Compound,PkScenario,PkPlannedDose
)


class TemplateDose(BaseModel):
    planned_at:datetime
    amount_mg:float=Field(gt=0,le=10000)


class Template(BaseModel):
    format:str
    compound_id:int|None=Field(default=None,gt=0)
    compound_name:str=Field(
        min_length=1,max_length=120
    )
    name:str=Field(min_length=1,max_length=160)
    half_life_hours:float=Field(gt=0,le=10000)
    absorption_half_life_hours:float=Field(
        gt=0,le=10000
    )
    doses:list[TemplateDose]=Field(
        max_length=300
    )

    @model_validator(mode='after')
    def validate_all(self):
        if self.format!=(
            'tracker-pk-scenario-template-v1'
        ):
            raise ValueError(
                'Unsupported scenario template'
            )

        timestamps=[
            x.planned_at for x in self.doses
        ]

        if len(timestamps)!=len(set(timestamps)):
            raise ValueError(
                'Duplicate administration times'
            )

        return self


def validate(db,data):
    from sqlalchemy import select

    clean=data.compound_name.strip().casefold()

    candidate=(
        db.get(Compound,data.compound_id)
        if data.compound_id else None
    )

    if (
        candidate is not None
        and candidate.name.strip().casefold()==clean
    ):
        return candidate

    matches=[
        c for c in db.scalars(select(Compound))
        if c.name.strip().casefold()==clean
    ]

    if len(matches)!=1:
        raise HTTPException(
            400,
            'Compound name must match exactly one installed compound'
        )

    return matches[0]


def create(db,data):
    compound=validate(db,data)

    scenario=PkScenario(
        compound_id=compound.id,
        name=data.name,
        half_life_hours=data.half_life_hours,
        absorption_half_life_hours=
            data.absorption_half_life_hours
    )

    db.add(scenario)
    db.flush()

    for dose in data.doses:
        db.add(PkPlannedDose(
            scenario_id=scenario.id,
            planned_at=dose.planned_at,
            amount_mg=dose.amount_mg
        ))

    from .pk_scenario_version import audit, snapshot
    db.flush()
    audit(
        db,scenario.id,"scenario_import",
        {},snapshot(db,scenario)
    )
    db.commit()

    return {
        'id':scenario.id,
        'count':len(data.doses)
    }
