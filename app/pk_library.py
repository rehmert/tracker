"""Named PK experiments stored with backed-up Tracker uploads.

Only experiment definitions are written, never medical records.
The backup system already includes files below data/uploads.
"""
import fcntl
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, Field

from . import config
from .pk_workbench import ExperimentInput


class ExperimentSave(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    notes: str = Field(default="", max_length=1000)
    settings: ExperimentInput


def storage(pid):
    folder = config.DATA_DIR / "uploads" / "experiments"
    if folder.is_symlink():
        raise HTTPException(500,"Unsafe experiment storage")
    folder.mkdir(parents=True, exist_ok=True)
    if folder.is_symlink():
        raise HTTPException(500,"Unsafe experiment storage")
    return folder / f"protocol-{int(pid)}.json"


def _read(path):
    if path.is_symlink():
        raise HTTPException(500,"Unsafe experiment file")
    if not path.exists():
        return []
    if path.stat().st_size > 2_000_000:
        raise HTTPException(500,"Experiment storage limit exceeded")
    data = json.loads(path.read_text())
    if not isinstance(data,list) or len(data)>100:
        raise HTTPException(500,"Invalid experiment library")
    return data


def _edit(pid, callback):
    path = storage(pid)
    lock = path.with_suffix(".lock")
    if lock.is_symlink():
        raise HTTPException(500,"Unsafe experiment lock")
    with lock.open("a+") as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        rows = _read(path)
        updated, response = callback(rows)
        if updated is not None:
            if len(updated)>100:
                raise HTTPException(400,"Maximum 100 experiments")
            payload = json.dumps(
                updated, ensure_ascii=False, indent=2
            )
            if len(payload.encode())>2_000_000:
                raise HTTPException(400,"Experiment library too large")
            fd, tmp = tempfile.mkstemp(
                prefix=".pk-",dir=path.parent
            )
            try:
                os.fchmod(fd,0o600)
                with os.fdopen(fd,"w") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(tmp,path)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
        return response


def listing(pid):
    return _edit(pid, lambda rows:(None,rows))


def source_snapshot(protocol):
    fields=(
        "compound_id","amount_value","amount_unit",
        "freq_count","freq_period","start_week",
        "end_week","dose_days","dose_time",
    )
    return {
        "name":protocol.name,
        "start_date":(
            protocol.start_date.isoformat()
            if protocol.start_date else None
        ),
        "end_date":(
            protocol.end_date.isoformat()
            if protocol.end_date else None
        ),
        "items":[
            {field:getattr(item,field) for field in fields}
            for item in protocol.items
        ],
    }


def revise(pid,identifier,protocol,entry):
    def operation(rows):
        for row in rows:
            if row.get("id")!=identifier:
                continue
            before={
                k:v for k,v in row.items()
                if k!="revisions"
            }
            history=row.get("revisions",[])+[before]
            if len(history)>20:
                raise HTTPException(
                    400,"Maximum 20 revisions per experiment"
                )
            new=dict(
                row,
                name=entry.name.strip(),
                notes=entry.notes,
                settings=entry.settings.model_dump(),
                saved_at=datetime.now(
                    timezone.utc
                ).isoformat(),
                source_updated_at=(
                    protocol.updated_at.isoformat()
                    if protocol.updated_at else None
                ),
                source_snapshot=source_snapshot(protocol),
                revisions=history,
            )
            return [
                new if x.get("id")==identifier else x
                for x in rows
            ],new
        raise HTTPException(404,"Experiment not found")
    return _edit(pid,operation)


def save(pid,protocol,entry):
    def operation(rows):
        row = {
            "id":uuid4().hex,
            "name":entry.name.strip(),
            "notes":entry.notes,
            "saved_at":datetime.now(
                timezone.utc
            ).isoformat(),
            "source_updated_at":(
                protocol.updated_at.isoformat()
                if protocol.updated_at else None
            ),
            "settings":entry.settings.model_dump(),
            "source_snapshot":source_snapshot(protocol),
            "revisions":[],
        }
        return rows+[row],row
    return _edit(pid,operation)


def delete(pid,identifier):
    def operation(rows):
        remaining = [
            row for row in rows
            if row.get("id") != identifier
        ]
        if len(remaining)==len(rows):
            raise HTTPException(404,"Experiment not found")
        return remaining,{"ok":True}
    return _edit(pid,operation)
