"""Descriptive cross-domain analytics. No dosing or causal recommendations."""
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from statistics import mean, median
import json
from math import isfinite

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from . import pk, config, metrics, labs
from .models import (Compound, Vial, DoseLog, Blend, BlendDose, BlendComponent, RegimenEntry,
                     RegimenItem, VitalReading, LabReport, LabResult, ChangeAudit)
from .blend_administration_view import blend_dose_components
from .progress_calc762 import daily_weights762, weight_report762
from .progress_models762 import ProgressSettings762, ProgressMeasure762, ProgressComposition762, ProgressMarker762
from .wellness_models807 import WellnessDay807, Symptom807, SiteReaction807
from .wellness807 import METRICS, metric_summary
from .site_history807 import history807
from .workout_models654 import WorkoutSession654, WorkoutSet654

def actual_compound807(db, cid, start, end):
    """Use existing base amounts and blend constituent projection; mass only."""
    singles=db.execute(select(DoseLog.taken_at,DoseLog.amount_base,Vial.content_unit)
        .join(Vial,DoseLog.vial_id==Vial.id).where(Vial.compound_id==cid,DoseLog.kind=="dose",
            DoseLog.taken_at>=start,DoseLog.taken_at<=end)).all()
    result=[(at,amount/1000) for at,amount,unit in singles
            if unit in ("mg","mcg","g") and isfinite(amount) and amount>0]
    query=(select(BlendDose).where(BlendDose.kind=="dose",BlendDose.taken_at>=start,
              BlendDose.taken_at<=end,BlendDose.blend_id.in_(
              select(BlendComponent.blend_id).where(BlendComponent.compound_id==cid)))
           .options(selectinload(BlendDose.blend).selectinload(Blend.components).selectinload(BlendComponent.compound),
                    selectinload(BlendDose.blend).selectinload(Blend.components).selectinload(BlendComponent.source_vial)))
    for draw in db.scalars(query):
        for part in blend_dose_components(draw):
            if part["compound_id"]==cid and part["unit"]=="mcg" and isfinite(part["amount"]) and part["amount"]>0:
                result.append((draw.taken_at,part["amount"]/1000))
    return sorted(result)

def cycle_samples807(observations, administrations):
    """Actual elapsed hours; exclude observations with no preceding actual."""
    from bisect import bisect_right
    stamps=[at for at,amount in administrations]
    result=[]
    for at,value in observations:
        i=bisect_right(stamps,at)-1
        if i>=0:
            elapsed=(at-stamps[i]).total_seconds()/3600
            result.append((at,value,elapsed,administrations[i][1]))
    return result

def cycle_summary807(samples):
    grouped=defaultdict(list)
    for at,value,hours,amount in samples:
        # Preserve elapsed time, rather than presuming every regimen is weekly.
        bucket=int(hours//24)
        grouped[bucket].append(value)
    return [dict(start_hours=day*24,end_hours=(day+1)*24,count=len(values),
                 average=round(mean(values),3)) for day,values in sorted(grouped.items())]

def periods807(actual):
    """Descriptive observed amount/interval runs, not inferred prescriptions."""
    if not actual:
        return []
    groups=[]
    current=[actual[0]]
    gaps=[]
    for event in actual[1:]:
        at,amount=event
        last,previous=current[-1]
        gap=(at-last).total_seconds()/3600
        changed=abs(amount-previous)>max(1e-8,abs(previous)*.001)
        interval_changed=bool(len(gaps)>=2 and abs(gap-median(gaps))>max(12,median(gaps)*.25))
        if changed or interval_changed:
            groups.append((current,gaps))
            current,gaps=[event],[]
        else:
            current.append(event)
            gaps.append(gap)
    groups.append((current,gaps))
    return [dict(start=events[0][0],end=events[-1][0],count=len(events),
                 amount_mg=events[0][1],median_hours=median(gaps) if gaps else None,
                 min_hours=min(gaps) if gaps else None,max_hours=max(gaps) if gaps else None)
            for events,gaps in groups]

def outcome_points807(db,key,start,end,nutrition=()):
    if key in METRICS:
        rows=db.scalars(select(WellnessDay807).where(WellnessDay807.day>=start.date(),
            WellnessDay807.day<=end.date()).order_by(WellnessDay807.day))
        result=[]
        for row in rows:
            value=json.loads(row.values_json).get(key)
            at=datetime.combine(row.day,time(12))
            if value is not None and at<=end:
                result.append((at,value))
        return result
    if key in ("calories","protein"):
        name="energy" if key=="calories" else "protein"
        return [(datetime.combine(row["date"],time(12)),row[name]) for row in nutrition
                if row.get("complete_"+name) and start.date()<=row["date"]<=end.date()
                and datetime.combine(row["date"],time(12))<=end]
    if key=="symptom_severity":
        return [(r.onset_at,r.severity) for r in db.scalars(select(Symptom807)
                .where(Symptom807.onset_at>=start,Symptom807.onset_at<=end).order_by(Symptom807.onset_at))]
    if key.startswith("lab:"):
        name=key[4:]
        rows=db.execute(select(LabResult,LabReport.drawn_on).join(LabReport)
            .where(LabReport.drawn_on>=start.date(),LabReport.drawn_on<=end.date())).all()
        matches=[(r,d) for r,d in rows if labs.analyte_key(r.analyte)==name]
        if not matches:
            return []
        series=labs.build_series(matches[0][0].analyte,[labs.Point(d,r.value,r.unit,r.ref_low,r.ref_high) for r,d in matches])
        return [(at,value) for at,value in series.points if at<=end]
    col={"weight":VitalReading.weight_kg,"systolic":VitalReading.systolic,
         "diastolic":VitalReading.diastolic,"pulse":VitalReading.pulse_bpm}.get(key)
    if col is None:
        return []
    points=db.execute(select(VitalReading.measured_at,col).where(VitalReading.measured_at>=start,
        VitalReading.measured_at<=end,col.is_not(None)).order_by(VitalReading.measured_at)).all()
    return [(at,metrics.weight_from_kg(v,config.WEIGHT_UNIT) if key=="weight" else v) for at,v in points]

def effectiveness807(db, cid, key, start, end, nutrition=()):
    compound=db.get(Compound,cid) if cid else None
    observed=outcome_points807(db,key,start,end,nutrition)
    empty=dict(observed=observed,paired=[],cycles=[],periods=[],model=None,actual_count=0,
               reason="Choose a compound.")
    if compound is None:
        return empty
    profile=pk.profile(compound.name)
    model=pk.model_info(compound.name) if profile else None
    actual=actual_compound807(db,cid,start-timedelta(days=365),end)
    within=[a for a in actual if a[0]>=start]
    samples=cycle_samples807(observed,actual)
    periods=periods807(within)
    for i,period in enumerate(periods):
        until=periods[i+1]["start"] if i+1<len(periods) else end+timedelta(seconds=1)
        subset=[v for at,v in observed if period["start"]<=at<until]
        period["outcome_count"]=len(subset)
        period["outcome_mean"]=round(mean(subset),3) if subset else None
        n=[r for r in nutrition if period["start"].date()<=r["date"]<until.date()]
        for field in ("energy","protein"):
            values=[r[field] for r in n if r.get("complete_"+field)]
            period[field+"_mean"]=round(mean(values),2) if values else None
        weights=db.execute(select(VitalReading.measured_at,VitalReading.weight_kg)
             .where(VitalReading.measured_at>=period["start"],VitalReading.measured_at<until,
                    VitalReading.weight_kg.is_not(None)).order_by(VitalReading.measured_at)).all()
        period["weight_count"]=len(weights)
        period["weight_change"]=metrics.weight_from_kg(weights[-1][1]-weights[0][1],config.WEIGHT_UNIT) if len(weights)>1 else None
        # Document concurrent administration of other compounds in the period.
        other=db.execute(select(Compound.name).join(Vial,Vial.compound_id==Compound.id)
            .join(DoseLog,DoseLog.vial_id==Vial.id).where(Compound.id!=cid,DoseLog.kind=="dose",
                   DoseLog.taken_at>=period["start"],DoseLog.taken_at<until).distinct()).scalars().all()
        period["concurrent"]=sorted(other)
    if not profile or model["needs_assumptions"]:
        paired=[]
        reason="No supported default model or explicit assumptions are required. Cycle observations remain descriptive."
    elif len(actual)>5000 or len(samples)>5000 or len(actual)*len(samples)>1_000_000:
        paired=[]
        reason="Exposure calculation withheld: choose a shorter range."
    else:
        paired=[dict(at=at,value=value,hours=round(hours,1),
                     exposure=round(pk.exposure_at(at,actual,*profile),5)) for at,value,hours,amount in samples]
        reason="Simulated mg-equivalent exposure; not measured serum concentration."
    return dict(observed=observed,paired=paired,cycles=cycle_summary807(samples),periods=periods,
                model=model,actual_count=len(within),reason=reason)

def site_analytics807(db,start,end,**filters):
    rows,truncated=history807(db,start,end,limit=5000,**filters)
    ids=defaultdict(list)
    for row in rows:
        ids[row["source"]].append(row["id"])
    reactions=[]
    if ids["dose"]:
        reactions.extend(db.scalars(select(SiteReaction807).where(SiteReaction807.dose_id.in_(ids["dose"]))))
    if ids["blend"]:
        reactions.extend(db.scalars(select(SiteReaction807).where(SiteReaction807.blend_dose_id.in_(ids["blend"]))))
    reports=defaultdict(list)
    for reaction in reactions:
        key=("dose",reaction.dose_id) if reaction.dose_id else ("blend",reaction.blend_dose_id)
        reports[key].append(reaction)
    groups=defaultdict(list)
    for row in rows:
        groups[row["site"] or ""].append(row)
    stats=[]
    for site,items in groups.items():
        stamps=sorted(r["at"] for r in items)
        gaps=[(b-a).total_seconds()/3600 for a,b in zip(stamps,stamps[1:])]
        linked=[reports[(r["source"],r["id"])] for r in items if (r["source"],r["id"]) in reports]
        stats.append(dict(site=site,count=len(items),last=stamps[-1],
            average_hours=round(mean(gaps),1) if gaps else None,
            reactions=sum(r.severity>0 for group in linked for r in group),
            reported=len(linked),recent=sum(r["at"]>=end-timedelta(days=7) for r in items)))
    return dict(rows=rows[:200],stats=sorted(stats,key=lambda r:(-r["count"],r["site"])),
                count=len(rows),truncated=truncated,reports=reports)

def weekly_report807(db, start, end, nutrition=()):
    days=(end.date()-start.date()).days+1
    wellness=list(db.scalars(select(WellnessDay807).where(WellnessDay807.day>=start.date(),WellnessDay807.day<=end.date())))
    symptoms=list(db.scalars(select(Symptom807).where(Symptom807.onset_at>=start,Symptom807.onset_at<=end)))
    vitals=list(db.scalars(select(VitalReading).where(VitalReading.measured_at>=start-timedelta(days=90),
                     VitalReading.measured_at<=end).order_by(VitalReading.measured_at,VitalReading.id)))
    period_vitals=[r for r in vitals if r.measured_at>=start]
    settings=db.get(ProgressSettings762,1)
    weight=weight_report762(daily_weights762(vitals),end.date(),
            settings.starting_weight_kg if settings else None,settings.goal_weight_kg if settings else None)
    period_weights=daily_weights762(period_vitals)
    weight["period_delta"]=period_weights[-1][1]-period_weights[0][1] if len(period_weights)>1 else None
    latest_measure=db.scalar(select(ProgressMeasure762).where(ProgressMeasure762.measured_on<=end.date(),
        ProgressMeasure762.waist_navel.is_not(None)).order_by(ProgressMeasure762.measured_on.desc(),ProgressMeasure762.id.desc()).limit(1))
    latest_comp=db.scalar(select(ProgressComposition762).where(ProgressComposition762.measured_on<=end.date())
        .order_by(ProgressComposition762.measured_on.desc(),ProgressComposition762.id.desc()).limit(1))
    nutrition_stats={}
    for field in ("energy","protein"):
        values=[r[field] for r in nutrition if r.get("complete_"+field)]
        nutrition_stats[field]=dict(count=len(values),average=round(mean(values),2) if values else None)
    sessions=db.scalar(select(func.count(WorkoutSession654.id)).where(
        WorkoutSession654.completed_at>=start,WorkoutSession654.completed_at<=end)) or 0
    volume=db.execute(select(func.count(WorkoutSet654.id),func.sum(WorkoutSet654.weight_lb*WorkoutSet654.reps))
        .join(WorkoutSession654,WorkoutSet654.session_id==WorkoutSession654.id)
        .where(WorkoutSession654.completed_at>=start,WorkoutSession654.completed_at<=end)).one()
    med_entries=db.execute(select(RegimenEntry.outcome,func.count(RegimenEntry.id))
        .where(RegimenEntry.logged_at>=start,RegimenEntry.logged_at<=end).group_by(RegimenEntry.outcome)).all()
    regimen=list(db.scalars(select(RegimenItem).where(RegimenItem.active.is_(True)).order_by(RegimenItem.kind,RegimenItem.name)))
    # Reuse actual calendar reconciliation, never count planned events as administrations.
    from .routers.calendar import _month_events
    schedule=Counter()
    cursor=start.date().replace(day=1)
    while cursor<=end.date():
        _,next_month,events,_=_month_events(cursor,db,include_vial_choices=False)
        for day,items in events.items():
            if start.date()<=day<=end.date():
                schedule.update(e["status"] for e in items if e.get("protocol_item_id") is not None)
        cursor=next_month
    site=site_analytics807(db,start,end)
    lab_rows=db.execute(select(LabResult,LabReport.drawn_on).join(LabReport)
        .where(LabReport.drawn_on<=end.date()).order_by(LabReport.drawn_on.desc(),LabResult.id.desc()).limit(1000)).all()
    seen={}
    for row,day in lab_rows:
        key=(labs.analyte_key(row.analyte),row.unit)
        if key not in seen:
            seen[key]=dict(name=row.analyte,date=day,value=row.value,unit=row.unit,previous=None)
        elif seen[key]["previous"] is None and day<seen[key]["date"]:
            seen[key]["previous"]=row.value
    expiry=list(db.scalars(select(Vial).where(Vial.status.in_(("sealed","in_use")),
        ((Vial.expires_on.is_not(None)) & (Vial.expires_on<=end.date()+timedelta(days=30))) |
        ((Vial.beyond_use_on.is_not(None)) & (Vial.beyond_use_on<=end.date()+timedelta(days=30))))
        .order_by(Vial.id).limit(100)))
    changes=list(db.scalars(select(ProgressMarker762).where(ProgressMarker762.measured_on>=start.date(),
        ProgressMarker762.measured_on<=end.date()).order_by(ProgressMarker762.measured_on).limit(100)))
    def avg(attr):
        values=[getattr(r,attr) for r in period_vitals if getattr(r,attr) is not None]
        return dict(count=len(values),average=round(mean(values),1) if values else None)
    return dict(days=days,wellness=metric_summary(wellness),wellness_days=len(wellness),
         symptoms=Counter(r.symptom for r in symptoms),symptom_rows=symptoms,
         weight=weight,measure=latest_measure,composition=latest_comp,nutrition=nutrition_stats,
         workouts=sessions,sets=volume[0],volume=volume[1],intake=dict(med_entries),regimen=regimen,
         scheduled=dict(schedule),site=site,lab=list(seen.values())[:60],
         systolic=avg("systolic"),diastolic=avg("diastolic"),pulse=avg("pulse_bpm"),
         expiry=expiry,changes=changes)
