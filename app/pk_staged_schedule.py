"""Validated hypothetical staged schedule projection."""
from datetime import datetime,timedelta
from pydantic import BaseModel,Field,model_validator
from fastapi import HTTPException


class Stage(BaseModel):
    amount_mg:float=Field(gt=0,le=10000)
    count:int=Field(ge=1,le=100)
    interval_days:float=Field(
        default=7,ge=.125,le=90
    )


class StagedInput(BaseModel):
    start_at:datetime
    stages:list[Stage]=Field(
        min_length=1,max_length=8
    )
    expected_version:str|None=None

    @model_validator(mode='after')
    def limit(self):
        if sum(s.count for s in self.stages)>200:
            raise ValueError('Maximum 200 doses')
        return self


def project(data):
    at=data.start_at
    result=[]

    for number,stage in enumerate(data.stages,1):
        for _ in range(stage.count):
            result.append({
                'stage':number,
                'planned_at':at.isoformat(),
                'amount_mg':stage.amount_mg
            })
            at+=timedelta(days=stage.interval_days)

    times=[row['planned_at'] for row in result]

    if len(times)!=len(set(times)):
        raise HTTPException(
            400,'Generated timestamps overlap'
        )

    return result
