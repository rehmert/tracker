"""Deterministic Release 807 goal milestones and guarded trend projections."""
from datetime import timedelta
from math import isfinite, ceil
from statistics import mean

DEFAULT_MILESTONES = tuple(range(5, 100, 5))

def milestone_percentages807(raw):
    if not raw.strip():
        return DEFAULT_MILESTONES
    try:
        values = tuple(sorted({float(part.strip()) for part in raw.split(",")}))
    except ValueError:
        raise ValueError("Enter comma-separated percentages.") from None
    if not values or len(values)>30 or any(not isfinite(v) or not 0<v<100 for v in values):
        raise ValueError("Milestones must be between 0 and 100 percent.")
    return values

def milestones807(observed, baseline, goal, percentages=DEFAULT_MILESTONES):
    if baseline is None or baseline <= 0:
        return []
    result=[]
    max_goal = (baseline-goal)/baseline*100 if goal is not None and 0<goal<baseline else None
    for percent in percentages:
        threshold=baseline*(1-percent/100)
        reached=next((day for day,value in observed if value<=threshold),None)
        if max_goal is not None and percent>max_goal and not reached:
            if any(r["reached"] is None and r["percent"]>max_goal for r in result):
                continue
        result.append(dict(percent=percent, threshold=threshold, reached=reached))
    return result

def projections807(observed, today, goal):
    result=[]
    for days in (14,30,60,90):
        samples=[(d,v) for d,v in observed if today-timedelta(days=days-1)<=d<=today and isfinite(v) and v>0]
        item=dict(days=days,count=len(samples),goal_date=None,reason="Insufficient recorded coverage",weekly_rate=None)
        if goal is None or goal<=0:
            item["reason"]="Set a weight goal"
        elif samples and samples[-1][1]<=goal:
            item["reason"]="Latest recorded weight is at or below goal"
        elif len(samples)>=max(4,ceil(days*.25)) and (samples[-1][0]-samples[0][0]).days>=days*.5 and (today-samples[-1][0]).days<=7:
            x=[(d-samples[-1][0]).days for d,v in samples]
            y=[v for d,v in samples]
            mx,my=mean(x),mean(y)
            variance=sum((v-mx)**2 for v in x)
            slope=sum((a-mx)*(b-my) for a,b in zip(x,y))/variance if variance else 0
            latest=samples[-1][1]
            item["weekly_rate"]=7*slope
            fraction=-7*slope/latest
            if fraction<.001:
                item["reason"]="Flat or increasing trend"
            elif fraction>.015:
                item["reason"]="Short-term decline is too steep to extrapolate"
            else:
                projected=ceil((latest-goal)/(-slope))
                if projected>730:
                    item["reason"]="Projection exceeds two years"
                else:
                    item["goal_date"]=samples[-1][0]+timedelta(days=projected)
                    if item["goal_date"]<today:
                        item["goal_date"]=None
                        item["reason"]="Projection predates current date"
                    else:
                        item["reason"]="Linear continuation of recorded trend"
        result.append(item)
    return result
