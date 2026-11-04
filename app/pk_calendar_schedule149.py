"""Weekday-local hypothetical scheduling with DST diagnostics."""
from datetime import date,datetime,time,timedelta,timezone
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from fastapi import HTTPException
from pydantic import BaseModel,Field,model_validator


class CalendarRule(BaseModel):
    start:date
    end:date
    weekdays:list[int]=Field(
        min_length=1,max_length=7
    )
    local_time:time
    amount_mg:float=Field(gt=0,le=10000)
    timezone_name:str=Field(
        default='America/New_York',
        min_length=1,max_length=80
    )
    expected_version:str|None=None

    @model_validator(mode='after')
    def validated(self):
        if (
            self.end<self.start
            or (self.end-self.start).days>365
        ):
            raise ValueError(
                'Calendar window must be 0 to 365 days'
            )

        if (
            len(set(self.weekdays))!=len(self.weekdays)
            or any(d not in range(7) for d in self.weekdays)
        ):
            raise ValueError(
                'Unique weekday indices 0–6 required'
            )

        if self.local_time.tzinfo is not None:
            raise ValueError(
                'Supply a wall-clock time, not an offset'
            )

        return self


def project(rule):
    try:
        zone=ZoneInfo(rule.timezone_name)
    except (ZoneInfoNotFoundError,ValueError,KeyError):
        raise HTTPException(400,'Unknown timezone')

    events=[]
    warnings=[]
    day=rule.start

    while day<=rule.end:
        if day.weekday() in rule.weekdays:
            local=datetime.combine(
                day,rule.local_time
            )
            offsets=[]

            for fold in (0,1):
                aware=local.replace(
                    tzinfo=zone,fold=fold
                )
                back=(
                    aware.astimezone(timezone.utc)
                    .astimezone(zone)
                    .replace(tzinfo=None)
                )

                if back==local:
                    offsets.append(
                        aware.utcoffset()
                    )

            if not offsets:
                warnings.append(
                    f'{day.isoformat()} '
                    f'{rule.local_time}: '
                    'nonexistent local time (DST gap)'
                )
            else:
                if len(set(offsets))>1:
                    warnings.append(
                        f'{day.isoformat()} '
                        f'{rule.local_time}: '
                        'ambiguous local time '
                        '(DST fold; first occurrence used)'
                    )

                events.append({
                    'planned_at':local.isoformat(),
                    'amount_mg':rule.amount_mg
                })

        day+=timedelta(days=1)

    if len(events)>200:
        raise HTTPException(
            400,
            'Limit calendar schedules to 200 administrations'
        )

    return {
        'doses':events,
        'warnings':warnings,
        'timezone':rule.timezone_name
    }
