"""Time-weighted modeled exposure statistics, never clinical concentrations."""
from datetime import datetime
from math import isfinite
from fastapi import HTTPException

def resolution(half_life_hours):
    if not isfinite(half_life_hours) or half_life_hours<=0:
        raise HTTPException(400,'Invalid half-life')
    return 0.5 if half_life_hours<4 else (1 if half_life_hours<24 else (6 if half_life_hours<96 else 12))

def metrics(rows,key='planned'):
    if len(rows)<2: raise HTTPException(400,'Insufficient samples')
    times=[datetime.fromisoformat(row['at']) for row in rows]
    values=[float(row[key]) for row in rows]
    if any(not isfinite(x) for x in values): raise HTTPException(400,'Nonfinite exposure')
    area=0.0
    for i in range(1,len(rows)):
        hours=(times[i]-times[i-1]).total_seconds()/3600
        if hours<=0: raise HTTPException(400,'Nonmonotonic timeline')
        area+=(values[i-1]+values[i])*hours/2
    duration=(times[-1]-times[0]).total_seconds()/3600
    return {'peak':max(values),'trough':min(values),'mean':area/duration,'auc':area,'hours':duration,
            'units':'modeled mg-equivalent exposure'}
