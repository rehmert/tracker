"""Workspace-local Google Tasks reconciliation.

No background network calls until OAuth and explicit enablement. Regimen intakes and strictly unambiguous user-completed protocol tasks
are reconciled. Other protocol completions require review.
"""
import fcntl
import hashlib
import json
import os
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from . import config
from .db import SessionLocal
from .google_tasks_client769 import TasksClient769, GoogleTasksError769, configured769
from .google_tasks_models769 import (GoogleTasksConnection769, GoogleTasksList769,
                                      GoogleTasksLink769, GoogleTasksExclusion769)
from .google_tasks_projection769 import projected769, KINDS
from .models import RegimenEntry, RegimenSchedule, RegimenTabletSchedule731, RegimenTabletEntry731
from .routers.regimen635 import _audit, _entry_snapshot
from .inventory_lock import reserve_inventory_write
from .google_protocol_review783 import auto_reconcile783

EASTERN = ZoneInfo("America/New_York")
LIST_NAMES = {
    "medication": "Medications", "supplement": "Supplements", "protocol": "Protocols",
}


@contextmanager
def exclusive769():
    lock = config.DATA_DIR / ".google-tasks769.lock"
    fd = os.open(str(lock), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def connection769(db):
    value = db.get(GoogleTasksConnection769, 1)
    if value is None:
        value = GoogleTasksConnection769(id=1)
        db.add(value)
        db.flush()
    return value


def _fingerprint(body):
    return hashlib.sha256(json.dumps(
        {key: body[key] for key in ("title", "notes", "due")},
        sort_keys=True, ensure_ascii=False,
    ).encode()).hexdigest()


def _day_bounds(day):
    lo = datetime.combine(day, time.min)
    return lo, lo + timedelta(days=1)


def _matching_entry(db, schedule_id, day):
    lo, hi = _day_bounds(day)
    return db.scalar(select(RegimenEntry).where(
        RegimenEntry.schedule_id == schedule_id,
        RegimenEntry.logged_at >= lo, RegimenEntry.logged_at < hi,
    ).order_by(RegimenEntry.id.desc()).limit(1))


def _import_completed_regimen(db, link, remote):
    if link.imported_entry_id:
        return
    if not reserve_inventory_write(db):
        raise GoogleTasksError769("Tracker database busy; sync deferred")
    if _matching_entry(db, link.source_id, link.scheduled_on):
        return
    schedule = db.get(RegimenSchedule, link.source_id)
    if schedule is None or schedule.item.kind != link.kind:
        return
    completed = remote.get("completed")
    try:
        instant = datetime.fromisoformat(completed.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            raise ValueError
        local = instant.astimezone(EASTERN)
    except (TypeError, ValueError, AttributeError):
        local = datetime.now(EASTERN)
    # Associate to the original scheduled day; preserve the Google completion
    # instant in notes, since checking a task later is not proof of dose time.
    taken_at = datetime.combine(link.scheduled_on, local.time().replace(tzinfo=None))
    marker = "Google Tasks completion (" + link.key + ")"
    entry = RegimenEntry(
        item_id=schedule.item_id, schedule_id=schedule.id, logged_at=taken_at,
        outcome="taken", amount=schedule.amount, meal=schedule.meal or "",
        notes=marker + "; marked completed at " + local.isoformat(),
    )
    db.add(entry)
    db.flush()
    plan = db.get(RegimenTabletSchedule731, schedule.id)
    if plan is not None:
        db.add(RegimenTabletEntry731(
            entry_id=entry.id, tablet_strength_mg=plan.tablet_strength_mg,
            prescribed_dose_mg=plan.prescribed_dose_mg,
            tablets_taken=plan.tablets_planned,
            administered_dose_mg=plan.prescribed_dose_mg,
        ))
    _audit(db, "regimen_entry", entry.id, "create", after=_entry_snapshot(entry))
    link.imported_entry_id = entry.id
    db.commit()


def _ensure_lists(db, client):
    current = {v.kind: v for v in db.scalars(select(GoogleTasksList769))}
    # Never adopt similarly named lists with unknown ownership.
    ids = {}
    for kind in KINDS:
        if kind in current:
            ids[kind] = current[kind].list_id
            continue
        prefix = config.instance_label()
        if prefix not in ("DEV", "PROD"):
            raise GoogleTasksError769("TRACKER_INSTANCE must identify DEV or PROD")
        label = "Tracker " + prefix + " — " + LIST_NAMES[kind]
        remote = client.create_list(label)
        if not remote.get("id"):
            raise GoogleTasksError769("Google list creation failed")
        db.add(GoogleTasksList769(kind=kind, list_id=remote["id"]))
        db.commit()
        ids[kind] = remote["id"]
    return ids


def _sync_locked769(db):
    settings = configured769()
    conn = db.get(GoogleTasksConnection769, 1)
    if not settings or not conn or not conn.enabled or not conn.refresh_token:
        return {"status": "disabled", "created": 0, "imported": 0, "pending_protocols": 0}
    client = TasksClient769(conn.refresh_token)
    counts = {"status": "ok", "created": 0, "imported": 0, "pending_protocols": 0}
    try:
        lists = _ensure_lists(db, client)
        remote_by_list = {
            kind: {task["id"]: task for task in client.tasks(list_id)
                   if isinstance(task, dict) and task.get("id")}
            for kind, list_id in lists.items()
        }
        remote_by_marker = {}
        for kind, remote in remote_by_list.items():
            for task in remote.values():
                notes = task.get("notes") or ""
                for line in notes.splitlines():
                    if line.startswith("Tracker ID: t769:"):
                        remote_by_marker[(kind, line[len("Tracker ID: "):].strip())] = task
        today = date.today()
        occurrences = projected769(db, today, 14)
        excluded_sources = {
            (row.kind, row.source_id) for row in db.scalars(select(GoogleTasksExclusion769))
        }
        occurrences = {key: o for key, o in occurrences.items()
                       if (o.kind, o.source_id) not in excluded_sources}
        links = {row.key: row for row in db.scalars(select(GoogleTasksLink769))}
        # Import first. A completion is only trusted when an existing Tracker
        # linkage references this exact list and task ID.
        for link in links.values():
            remote = remote_by_list.get(link.kind, {}).get(link.task_id)
            if not remote or remote.get("deleted"):
                link.removed = True
                continue
            was_completed = link.last_status == "completed"
            link.last_status = remote.get("status", "needsAction")
            db.commit()  # Close read transaction before reserved regimen write.
            if link.last_status == "completed":
                if link.kind == "protocol":
                    if not was_completed:
                        auto_reconcile783(db, link.key, remote, _fingerprint)
                    if link.imported_entry_id is None:
                        counts["pending_protocols"] += 1
                elif link.kind in ("medication", "supplement"):
                    before = link.imported_entry_id
                    _import_completed_regimen(db, link, remote)
                    if not before and link.imported_entry_id:
                        counts["imported"] += 1
        db.commit()
        for key, occ in occurrences.items():
            body = occ.task_body()
            fp = _fingerprint(body)
            link = links.get(key)
            if link and link.removed:
                continue  # Explicit Google deletion is not silently undone.
            remote = (remote_by_list[occ.kind].get(link.task_id) if link else
                      remote_by_marker.get((occ.kind, key)))
            if link is None:
                if remote and remote.get("deleted"):
                    continue
                if not remote:
                    remote = client.create_task(lists[occ.kind], body)
                    counts["created"] += 1
                if not remote.get("id"):
                    raise GoogleTasksError769("Google did not return a task ID")
                link = GoogleTasksLink769(
                    key=key, kind=occ.kind, source_id=occ.source_id,
                    scheduled_on=occ.day, scheduled_time=occ.at_time,
                    list_id=lists[occ.kind], task_id=remote["id"],
                    last_status=remote.get("status", "needsAction"),
                    last_fingerprint=fp,
                )
                db.add(link)
                db.commit()  # Claim remote ID immediately; remote marker recovers crash windows.
                links[key] = link
                remote_by_list[occ.kind][remote["id"]] = remote
            if remote and not remote.get("deleted"):
                if remote.get("status") == "needsAction":
                    if (remote.get("title") != body["title"] or
                        remote.get("notes") != body["notes"] or
                        (remote.get("due") or "")[:10] != occ.day.isoformat()):
                        remote = client.patch_task(link.list_id, link.task_id, {
                            "title": body["title"], "notes": body["notes"], "due": body["due"]
                        })
                    if occ.kind in ("medication", "supplement"):
                        entry = _matching_entry(db, occ.source_id, occ.day)
                        if entry and entry.outcome == "taken":
                            remote = client.patch_task(link.list_id, link.task_id,
                                                       {"status": "completed"})
                link.last_status = remote.get("status", link.last_status)
                link.last_fingerprint = fp
                db.commit()
        # Schedule cancellation and per-source opt-out delete future OPEN
        # tasks only. Completed historical tasks stay intact.
        for key, link in links.items():
            if link.removed or link.scheduled_on < today or key in occurrences:
                continue
            remote = remote_by_list.get(link.kind, {}).get(link.task_id)
            if remote and not remote.get("deleted") and remote.get("status") == "needsAction":
                client.delete_task(link.list_id, link.task_id)
                link.removed = True
                db.commit()
        conn.last_sync_at = datetime.now(timezone.utc).replace(tzinfo=None)
        conn.last_error = ""
        db.commit()
        return counts
    finally:
        client.close()


def sync_once769():
    try:
        with exclusive769():
            with SessionLocal() as db:
                try:
                    return _sync_locked769(db)
                except GoogleTasksError769 as exc:
                    conn = db.get(GoogleTasksConnection769, 1)
                    db.rollback()
                    if conn:
                        conn.last_error = str(exc)[:160]
                        db.commit()
                    raise
    except BlockingIOError:
        return {"status": "busy", "created": 0, "imported": 0, "pending_protocols": 0}


def _sync_completions_locked780(db):
    """Read only previously linked Google tasks; import completed intakes.

    This deliberately does not create task lists, project 14 days, update
    titles, push tasks, or delete Google resources. The normal 5-minute sync
    retains those responsibilities and performs eventual full reconciliation.
    """
    conn = db.get(GoogleTasksConnection769, 1)
    if not configured769() or not conn or not conn.enabled or not conn.refresh_token:
        return {"status": "disabled", "created": 0, "imported": 0, "pending_protocols": 0}

    links = list(db.scalars(select(GoogleTasksLink769).where(
        GoogleTasksLink769.removed.is_(False),
        GoogleTasksLink769.last_status != "completed",
    )))
    saved_lists = {row.kind: row.list_id for row in db.scalars(select(GoogleTasksList769))}
    # Never create a list on a fast poll. Full reconciliation takes care of
    # missing lists and links.
    pending = [link for link in links
               if link.kind in saved_lists and
               link.list_id == saved_lists[link.kind]]
    counts = {"status": "ok", "created": 0, "imported": 0, "pending_protocols": 0}
    if not pending:
        return counts

    client = TasksClient769(conn.refresh_token)
    try:
        kinds = {link.kind for link in pending}
        remote_by_kind = {
            kind: {task["id"]: task for task in client.tasks(saved_lists[kind])
                   if isinstance(task, dict) and task.get("id")}
            for kind in kinds
        }
        for link in pending:
            remote = remote_by_kind[link.kind].get(link.task_id)
            if not remote or remote.get("deleted") or remote.get("status") != "completed":
                continue
            link.last_status = "completed"
            db.commit()  # Close read transaction before reserved regimen write.
            if link.kind == "protocol":
                auto_reconcile783(db, link.key, remote, _fingerprint)
                if link.imported_entry_id is None:
                    counts["pending_protocols"] += 1
            elif link.kind in ("medication", "supplement"):
                before = link.imported_entry_id
                _import_completed_regimen(db, link, remote)
                if before is None and link.imported_entry_id is not None:
                    counts["imported"] += 1
        db.commit()
        return counts
    finally:
        client.close()


def sync_completions_once780():
    """Fast, non-overlapping completion-only pass using the existing lock."""
    try:
        with exclusive769():
            with SessionLocal() as db:
                try:
                    return _sync_completions_locked780(db)
                except GoogleTasksError769 as exc:
                    conn = db.get(GoogleTasksConnection769, 1)
                    db.rollback()
                    if conn:
                        conn.last_error = str(exc)[:160]
                        db.commit()
                    raise
    except BlockingIOError:
        return {"status": "busy", "created": 0, "imported": 0, "pending_protocols": 0}
