"""Backward-compatible scenario snapshots and multiplicity-preserving diffs."""
from collections import Counter
from datetime import datetime
from pydantic import BaseModel,ConfigDict,Field,model_validator


class Dose(BaseModel):
    model_config=ConfigDict(extra='ignore')
    id:int|None=None
    planned_at:datetime
    amount_mg:float=Field(
        gt=0,le=10000,allow_inf_nan=False
    )


class Snapshot(BaseModel):
    model_config=ConfigDict(extra='ignore')
    format_version:int=Field(default=1,ge=1,le=1)
    compound_id:int=Field(gt=0)
    name:str=Field(min_length=1,max_length=160)
    half_life_hours:float=Field(
        gt=0,le=10000,allow_inf_nan=False
    )
    absorption_half_life_hours:float=Field(
        gt=0,le=10000,allow_inf_nan=False
    )
    doses:list[Dose]=Field(max_length=300)

    @model_validator(mode='after')
    def unique_dates(self):
        if len({
            d.planned_at for d in self.doses
        })!=len(self.doses):
            raise ValueError('Duplicate planned timestamps')
        return self


def dose_counts(items):
    return Counter(
        (x['planned_at'],float(x['amount_mg']))
        for x in items
    )


def changes(current,target):
    old=dose_counts(current['doses'])
    new=dose_counts(target['doses'])

    return {
        'added':sum((new-old).values()),
        'removed':sum((old-new).values()),
        'name_changed':
            current['name']!=target['name'],
        'half_life_changed':
            current['half_life_hours']!=
            target['half_life_hours'],
        'absorption_changed':
            current['absorption_half_life_hours']!=
            target['absorption_half_life_hours']
    }


def equivalent(current,target):
    result=changes(current,target)

    return not (
        result['added']
        or result['removed']
        or result['name_changed']
        or result['half_life_changed']
        or result['absorption_changed']
    )
