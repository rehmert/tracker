"""Reconcile user-completed Google protocol tasks without guessing inventory.

Existing link.imported_entry_id is an enduring receipt: positive for DoseLog,
negative for BlendDose. A corrected/deleted log never causes automatic replay.
All mutations are under the caller's SQLite write reservation.
"""
from datetime import datetime, date, time, timedelta
from math import isfinite
from zoneinfo import ZoneInfo

from sqlalchemy import select

from . import units as U, services
from .audit_helpers import record
from .google_tasks_models769 import GoogleTasksLink769
from .google_tasks_projection769 import projected769
from .models import ProtocolItem, Vial, DoseLog, Blend, BlendDose, BlendComponent
from .inventory_lock import reserve_inventory_write

EASTERN = ZoneInfo("America/New_York")


def pending_links783(db):
    return list(db.scalars(select(GoogleTasksLink769).where(
        GoogleTasksLink769.kind == "protocol",
        GoogleTasksLink769.last_status == "completed",
        GoogleTasksLink769.imported_entry_id.is_(None),
    ).order_by(GoogleTasksLink769.scheduled_on, GoogleTasksLink769.scheduled_time,
               GoogleTasksLink769.key)))


def occurrence783(db, link):
    if link.scheduled_on > datetime.now(EASTERN).date():
        return None
    return projected769(db, link.scheduled_on, 1).get(link.key)


def _existing783(db, item, day):
    lo = datetime.combine(day, time.min)
    hi = lo + timedelta(days=1)
    doses = list(db.scalars(select(DoseLog).join(Vial).where(
        Vial.compound_id == item.compound_id, DoseLog.kind == "dose",
        DoseLog.taken_at >= lo, DoseLog.taken_at < hi,
    )))
    blends = list(db.scalars(select(BlendDose).where(
        BlendDose.kind == "dose", BlendDose.taken_at >= lo, BlendDose.taken_at < hi,
        BlendDose.blend_id.in_(select(BlendComponent.blend_id).where(
            BlendComponent.compound_id == item.compound_id)),
    )))
    return doses, blends


def _claimed783(db, item, receipt):
    # One physical blend draw may legitimately satisfy distinct constituents,
    # but cannot satisfy two occurrences for the same constituent.
    links = db.scalars(select(GoogleTasksLink769).where(
        GoogleTasksLink769.kind == "protocol",
        GoogleTasksLink769.imported_entry_id == receipt,
    ))
    for link in links:
        other = db.get(ProtocolItem, link.source_id)
        if other is None or other.compound_id == item.compound_id:
            return True
    return False


def _vials783(db, item, day):
    vials = list(db.scalars(select(Vial).where(
        Vial.compound_id == item.compound_id, Vial.status == "in_use",
    ).order_by(Vial.id)))
    views = services.vial_views(db, vials)
    out = []
    for vial in vials:
        if (vial.closed_on or (vial.expires_on and vial.expires_on < day)
                or (vial.beyond_use_on and vial.beyond_use_on < day)
                or (vial.reconstituted_on and vial.reconstituted_on > day)
                or (vial.first_punctured_on and vial.first_punctured_on > day)
                or (vial.received_on and vial.received_on > day)):
            continue
        view = views[vial.id]
        try:
            unit = U.parse_unit(item.amount_unit)
            if unit.dim not in ("mass", "iu") or unit.dim != view.dim:
                continue
            amount = U.amount_to_vial_base(item.amount_value, item.amount_unit,
                                           view.dim, view.conc_per_ml)
            if (not isfinite(amount) or amount <= 0
                    or not isfinite(view.remaining_base)
                    or amount > view.remaining_base + 1e-7
                    or not view.conc_per_ml or not isfinite(view.conc_per_ml)
                    or view.conc_per_ml <= 0):
                continue
        except (ValueError, TypeError, OverflowError):
            continue
        out.append((vial, amount))
    return out


def _blend_possible783(db, item):
    return db.scalar(select(Blend.id).join(BlendComponent).where(
        Blend.status == "in_use", BlendComponent.compound_id == item.compound_id,
    ).limit(1)) is not None


def _receipt783(db, link, receipt):
    link.imported_entry_id = receipt
    record(db, "google_protocol_completion", link.source_id, "reconcile",
           after={"key": link.key, "record_id": receipt})


def _write783(db, link, item, vial, base, when, note):
    dose = DoseLog(vial_id=vial.id, taken_at=when, entered_value=item.amount_value,
                   entered_unit=U.parse_unit(item.amount_unit).name, amount_base=base,
                   kind="dose", site="", notes=note)
    db.add(dose)
    db.flush()
    _receipt783(db, link, dose.id)


def review_rows783(db):
    rows = []
    for link in pending_links783(db):
        item = db.get(ProtocolItem, link.source_id)
        row = {"link": link, "item": item, "choices": [], "vials": [],
               "when": "", "reason": "Schedule missing or changed; review history."}
        if item is not None:
            doses, blends = _existing783(db, item, link.scheduled_on)
            row["choices"] = [
                (f"dose:{d.id}", f"{d.taken_at:%H:%M} · {d.entered_value:g} {d.entered_unit} · vial #{d.vial_id}")
                for d in doses if not _claimed783(db, item, d.id)
            ] + [
                (f"blend:{d.id}", f"{d.taken_at:%H:%M} · blend #{d.blend_id} · {d.volume_ml:g} mL")
                for d in blends if not _claimed783(db, item, -d.id)
            ]
            occ = occurrence783(db, link)
            if row["choices"]:
                row["reason"] = "Match an existing administration to avoid recording it twice."
            elif occ is not None:
                row["vials"] = [v for v, _ in _vials783(db, item, link.scheduled_on)]
                row["reason"] = ("Confirm the actual vial, scheduled amount and administration time."
                                 if row["vials"] else "No eligible active vial; use Dose Workspace.")
            if link.scheduled_time:
                row["when"] = link.scheduled_on.isoformat() + "T" + link.scheduled_time
        rows.append(row)
    return rows


def reconcile_choice783(db, key, choice, when_text):
    link = db.get(GoogleTasksLink769, key)
    if (link is None or link.kind != "protocol" or link.last_status != "completed"
            or link.imported_entry_id is not None):
        raise ValueError("Completion is no longer awaiting review; reload the page.")
    item = db.get(ProtocolItem, link.source_id)
    if item is None:
        raise ValueError("Original protocol item is unavailable.")
    if link.scheduled_on > datetime.now(EASTERN).date():
        raise ValueError("Future administrations cannot be recorded.")
    doses, blends = _existing783(db, item, link.scheduled_on)
    kind, sep, raw_id = choice.partition(":")
    if not sep or not raw_id.isascii() or not raw_id.isdecimal() or len(raw_id) > 10:
        raise ValueError("Choose a valid administration source.")
    pk = int(raw_id)
    if kind in ("dose", "blend"):
        receipt = pk if kind == "dose" else -pk
        if (not any(d.id == pk for d in (doses if kind == "dose" else blends))
                or _claimed783(db, item, receipt)):
            raise ValueError("Existing administration is unavailable or already matched.")
        _receipt783(db, link, receipt)
        return
    if kind != "vial" or occurrence783(db, link) is None:
        raise ValueError("Schedule changed; use Dose Workspace to record the actual administration.")
    if (any(not _claimed783(db, item, d.id) for d in doses)
            or any(not _claimed783(db, item, -d.id) for d in blends)):
        raise ValueError("Review the existing same-day administration before creating another.")
    try:
        when = datetime.fromisoformat(when_text)
        if (when.tzinfo is not None or when.date() != link.scheduled_on
                or when > datetime.now(EASTERN).replace(tzinfo=None)):
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError("Enter the actual local administration time on the scheduled date.") from None
    for vial, base in _vials783(db, item, link.scheduled_on):
        if vial.id == pk:
            _write783(db, link, item, vial, base, when,
                      "Google Tasks completion; manually confirmed scheduled amount, source and administration time.")
            return
    raise ValueError("Selected vial is no longer eligible or has insufficient contents.")


def auto_reconcile783(db, key, remote, fingerprint):
    """Only new, same-day, exact remote schedule completions may auto-record.

    A check-off is not an independently verified administration timestamp.
    Store scheduled time with explicit provenance, never infer supplies/site.
    """
    db.rollback()
    if not reserve_inventory_write(db):
        return False
    try:
        link = db.get(GoogleTasksLink769, key)
        if (link is None or link.kind != "protocol" or link.last_status != "completed"
                or link.imported_entry_id is not None or link.removed):
            return False
        now = datetime.now(EASTERN)
        if link.scheduled_on != now.date() or not link.scheduled_time:
            return False
        try:
            completed = datetime.fromisoformat(remote.get("completed", "").replace("Z", "+00:00"))
            if completed.tzinfo is None:
                return False
            completed = completed.astimezone(EASTERN)
            when = datetime.combine(link.scheduled_on, time.fromisoformat(link.scheduled_time))
        except (ValueError, TypeError, AttributeError):
            return False
        if completed.date() != link.scheduled_on or not when <= completed.replace(tzinfo=None) <= now.replace(tzinfo=None):
            return False
        occ = occurrence783(db, link)
        if occ is None:
            return False
        body = occ.task_body()
        # Verify both the published payload and Google's unchanged title/notes/date.
        if (fingerprint(body) != link.last_fingerprint
                or remote.get("title") != body["title"]
                or remote.get("notes") != body["notes"]
                or (remote.get("due") or "")[:10] != link.scheduled_on.isoformat()):
            return False
        item = db.get(ProtocolItem, link.source_id)
        if item is None:
            return False
        same_day = [o for o in projected769(db, link.scheduled_on, 1).values()
                    if o.kind == "protocol"
                    and db.get(ProtocolItem, o.source_id).compound_id == item.compound_id]
        if len(same_day) != 1 or _blend_possible783(db, item):
            return False
        doses, blends = _existing783(db, item, link.scheduled_on)
        if doses or blends:
            return False
        # Do not choose between multiple in-use sources, even if only one has
        # enough recorded stock. Never open a sealed vial automatically.
        active = list(db.scalars(select(Vial.id).where(
            Vial.compound_id == item.compound_id, Vial.status == "in_use")))
        candidates = _vials783(db, item, link.scheduled_on)
        if len(active) != 1 or len(candidates) != 1:
            return False
        vial, base = candidates[0]
        _write783(db, link, item, vial, base, when,
                  "Google Tasks completion; scheduled amount/time, actual administration time not independently known; checked off "
                  + completed.isoformat())
        db.commit()
        return True
    finally:
        # On any early return or failure, close the reservation without writes.
        db.rollback()
