"""Read-only physical site history and explicitly configured rotation.

A blend is one physical administration regardless of constituent count.
No calendar projection, discard or preparation is counted.
"""
from datetime import datetime, timedelta
from collections import defaultdict
import json

from sqlalchemy import select, union_all, literal, func
from .models import DoseLog, BlendDose, Vial, Compound, Blend, BlendComponent, ProtocolItem, RegimenEntry, RegimenItem
from .wellness_models807 import AdministrationContext807 as Context, RotationPreference807, SiteExclusion807, SiteReaction807
from .anatomical_sites807 import SITE_BY_CODE, configured_rotation, next_rotation_site, site_label, valid_site

ROUTES = ("", "subcutaneous", "intramuscular", "other")

def save_context807(db, source, row, route=None, protocol_id=None, site=None):
    """Caller holds the original administration transaction; no extra commit."""
    column = {"dose": Context.dose_id, "blend": Context.blend_dose_id, "regimen": Context.regimen_entry_id}[source]
    old = db.scalar(select(Context).where(column == row.id))
    actual = row.outcome == "taken" if source == "regimen" else row.kind == "dose"
    if not actual:
        if old is not None:
            db.delete(old)
        return
    route = (old.route if old else "") if route is None else route
    if route not in ROUTES:
        raise ValueError("Unknown administration route.")
    if site is not None and not valid_site(site, previous=old.site if old else None):
        raise ValueError("Unknown injection site.")
    if not route and not protocol_id and old is None and not site:
        return
    if old is None:
        old = Context()
        setattr(old, column.key, row.id)
        db.add(old)
    old.route = route
    if protocol_id is not None:
        old.protocol_id = protocol_id
    # Existing vial/blend site fields are the sole location source.
    if source == "regimen" and site is not None:
        old.site = site

def context807(db, source, rid):
    column = {"dose": Context.dose_id, "blend": Context.blend_dose_id, "regimen": Context.regimen_entry_id}[source]
    return db.scalar(select(Context).where(column == rid))

def protocol_for_calendar807(db, item_id):
    if item_id is None:
        return None
    return db.scalar(select(ProtocolItem.protocol_id).where(ProtocolItem.id == item_id))

def physical_query807(*, compound=None, blend=None, protocol=None, route=None):
    dose = (select(literal("dose").label("source"), DoseLog.id.label("id"), DoseLog.taken_at.label("at"),
                   DoseLog.site.label("site"), Compound.name.label("name"),
                   func.coalesce(Context.route, "").label("route"), Context.protocol_id.label("protocol"))
            .join(Vial, DoseLog.vial_id == Vial.id).join(Compound, Vial.compound_id == Compound.id)
            .outerjoin(Context, Context.dose_id == DoseLog.id).where(DoseLog.kind == "dose"))
    mixed = (select(literal("blend").label("source"), BlendDose.id.label("id"), BlendDose.taken_at.label("at"),
                    BlendDose.site.label("site"), Blend.label.label("name"),
                    func.coalesce(Context.route, "").label("route"), Context.protocol_id.label("protocol"))
             .join(Blend, BlendDose.blend_id == Blend.id).outerjoin(Context, Context.blend_dose_id == BlendDose.id)
             .where(BlendDose.kind == "dose"))
    regimen = (select(literal("regimen").label("source"), RegimenEntry.id.label("id"),
                      RegimenEntry.logged_at.label("at"), Context.site.label("site"), RegimenItem.name.label("name"),
                      Context.route.label("route"), Context.protocol_id.label("protocol"))
               .join(RegimenItem, RegimenEntry.item_id == RegimenItem.id)
               .join(Context, Context.regimen_entry_id == RegimenEntry.id)
               .where(RegimenEntry.outcome == "taken", RegimenItem.kind == "medication"))
    if compound is not None:
        dose = dose.where(Vial.compound_id == compound)
        mixed = mixed.where(BlendDose.blend_id.in_(select(BlendComponent.blend_id).where(BlendComponent.compound_id == compound)))
        regimen = regimen.where(literal(False))
    if blend is not None:
        dose = dose.where(literal(False))
        mixed = mixed.where(BlendDose.blend_id == blend)
        regimen = regimen.where(literal(False))
    union = union_all(dose, mixed, regimen).subquery()
    query = select(union)
    if protocol is not None:
        query = query.where(union.c.protocol == protocol)
    if route is not None:
        query = query.where(union.c.route == route)
    return query, union

def history807(db, start, end, *, compound=None, blend=None, protocol=None, route=None, site=None, limit=1000):
    query, c = physical_query807(compound=compound, blend=blend, protocol=protocol, route=route)
    query = query.where(c.c.at >= start, c.c.at <= end)
    if site is not None:
        query = query.where(c.c.site == site)
    rows = db.execute(query.order_by(c.c.at.desc(), c.c.source, c.c.id.desc()).limit(limit+1)).mappings().all()
    return rows[:limit], len(rows)>limit

def last_use807(db, now):
    _, c = physical_query807()
    return dict(db.execute(select(c.c.site, func.max(c.c.at)).where(
        c.c.site.in_(tuple(SITE_BY_CODE)), c.c.at <= now).group_by(c.c.site)).all())

def rotation_key807(scope, identity, route):
    if scope not in ("global", "compound", "blend", "protocol") or route not in ROUTES:
        raise ValueError("Unknown rotation scope or route.")
    if scope == "global":
        if identity is not None:
            raise ValueError("Global rotation has no source ID.")
    elif not isinstance(identity, int) or not 0 < identity <= 2**63-1:
        raise ValueError("Select a valid source.")
    return f"{scope}:{identity or 0}:{route}"

def rotation_config807(db, route, *, compound=None, blend=None, protocol=None):
    for scope, identity in (("protocol", protocol), ("blend", blend), ("compound", compound), ("global", None)):
        if scope != "global" and identity is None:
            continue
        row = db.get(RotationPreference807, rotation_key807(scope, identity, route))
        if row is not None:
            return row
    return None

def site_snapshot807(db, now, *, compound=None, blend=None, protocol=None, route=""):
    last = last_use807(db, now)
    rows, truncated = history807(db, now-timedelta(days=90), now, limit=5000)
    totals = defaultdict(int)
    recent_names = {}
    for row in rows:
        if row["site"] in SITE_BY_CODE:
            totals[row["site"]] += 1
            recent_names.setdefault(row["site"], row["name"])
    reactions = db.execute(select(SiteReaction807.site, func.count(SiteReaction807.id))
        .where(SiteReaction807.onset_at >= now-timedelta(days=90), SiteReaction807.onset_at <= now,
               SiteReaction807.severity > 0, SiteReaction807.resolved_at.is_(None))
        .group_by(SiteReaction807.site)).all()
    active = dict(reactions)
    excluded = set(db.scalars(select(SiteExclusion807.site).where(SiteExclusion807.until_at > now)))
    settings = rotation_config807(db, route, compound=compound, blend=blend, protocol=protocol)
    sequence = tuple(json.loads(settings.sequence_json)) if settings else ()
    previous = max(last, key=last.get) if last else None
    next_site = next_rotation_site(sequence, previous, last, excluded, settings.minimum_hours if settings else 0, now)
    threshold = settings.recent_hours if settings else 72
    result = {}
    for code in SITE_BY_CODE:
        when = last.get(code)
        elapsed = (now-when).total_seconds()/3600 if when else None
        result[code] = dict(label=site_label(code), last=when.isoformat() if when else None,
            elapsed_hours=round(elapsed,1) if elapsed is not None else None,
            recent=elapsed is not None and elapsed < threshold, count=totals[code],
            last_name=recent_names.get(code), active_reactions=active.get(code,0),
            excluded=code in excluded, eligible=code in sequence and code not in excluded,
            next=code==next_site)
    return dict(sites=result, configured=settings is not None, next_site=next_site, truncated=truncated,
                last_site=previous, range_days=90)
