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
    compound_id:int=Field(gt=0)
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
    compound=db.get(
        Compound,data.compound_id
    )

    if (
        compound is None
        or compound.name.strip().casefold()
        !=data.compound_name.strip().casefold()
    ):
        raise HTTPException(
            400,
            'Compound name/ID mismatch'
        )

    return compound


def create(db,data):
    validate(db,data)

    scenario=PkScenario(
        compound_id=data.compound_id,
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
