from datetime import date, datetime
import json
from html import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import calc, services
from ..db import get_db
from ..models import Compound, Protocol, ProtocolItem, ProtocolRevision
from ..templating import render

router = APIRouter()
BLANK = {"amount_value": "", "amount_unit": "mg", "freq_count": 1, "freq_period": "week"}


def _saved_inputs(p: Protocol) -> list[calc.ItemInput]:
    return [calc.ItemInput(i.compound_id, i.amount_value, i.amount_unit, i.freq_count,
                           i.freq_period) for i in p.items]


def _evaluate(inputs: list[calc.ItemInput], refs: dict, weeks: float) -> list[calc.ItemResult]:
    return [calc.project_item(i, refs[i.compound_id], weeks * 7) for i in inputs]


def _parse_rows(refs, compound_id, amount, unit, freq_count, freq_period):
    """Returns (valid inputs, results for rows that failed to parse). Row order of
    the form is kept in the results list via the third element."""
    parsed: list[calc.ItemInput | calc.ItemResult] = []
    for cid, a, u, fc, fp in zip(compound_id, amount, unit, freq_count, freq_period):
        try:
            cid_i = int(cid)
        except ValueError:
            parsed.append(calc.invalid_result("Unknown compound", "Choose a compound."))
            continue
        ref = refs.get(cid_i)
        if ref is None:
            parsed.append(calc.invalid_result("Unknown compound", "Choose a compound."))
            continue
        try:
            parsed.append(calc.ItemInput(cid_i, float(a), u, float(fc), fp))
        except ValueError:
            parsed.append(calc.invalid_result(ref.name, "Enter a number for the amount and "
                                              "the frequency.", cid_i))
    return parsed


def _horizon(text: str) -> float:
    try:
        w = float(text)
    except ValueError:
        return 12.0
    return min(max(w, 0.1), 520.0)


@router.get("/protocols")
def protocols_page(request: Request, db: Session = Depends(get_db)):
    refs = services.compound_refs(db)
    rows = []
    for p in db.scalars(select(Protocol).order_by(Protocol.updated_at.desc())):
        t = calc.totals(_evaluate(_saved_inputs(p), refs, p.horizon_weeks))
        rows.append({"p": p, "t": t})
    return render(request, "protocols.html", rows=rows)


@router.post("/protocols")
def create_protocol(name: str = Form("New plan"), db: Session = Depends(get_db)):
    p = Protocol(name=name.strip() or "New plan")
    db.add(p)
    db.commit()
    return services.flash_redirect(f"/protocols/{p.id}")


@router.get("/protocols/row")
def blank_row(request: Request, db: Session = Depends(get_db)):
    compounds = list(db.scalars(select(Compound).order_by(Compound.name)))
    return render(request, "_protocol_row.html", item=dict(BLANK, compound_id=None),
                  compounds=compounds)


@router.get("/protocols/{pid}")
def protocol_editor(pid: int, request: Request, db: Session = Depends(get_db)):
    p = db.get(Protocol, pid)
    if p is None:
        raise HTTPException(404, "Protocol not found")
    compounds = list(db.scalars(select(Compound).order_by(Compound.name)))
    return render(request, "protocol_edit.html", p=p, compounds=compounds)


@router.post("/protocols/{pid}/calc")
def protocol_calc(pid: int, request: Request, horizon_weeks: str = Form("12"),
                  compound_id: list[str] = Form(default=[]), amount: list[str] = Form(default=[]),
                  unit: list[str] = Form(default=[]), freq_count: list[str] = Form(default=[]),
                  freq_period: list[str] = Form(default=[]), db: Session = Depends(get_db)):
    """Stateless what-if: recalculates from the form as it currently stands."""
    p = db.get(Protocol, pid)
    if p is None:
        raise HTTPException(404, "Protocol not found")
    refs = services.compound_refs(db)
    weeks = _horizon(horizon_weeks)
    results = []
    for entry in _parse_rows(refs, compound_id, amount, unit, freq_count, freq_period):
        if isinstance(entry, calc.ItemResult):
            results.append(entry)
        else:
            results.append(calc.project_item(entry, refs[entry.compound_id], weeks * 7))
    saved = calc.totals(_evaluate(_saved_inputs(p), refs, p.horizon_weeks)) if p.items else None
    return render(request, "_protocol_results.html", results=results, t=calc.totals(results),
                  saved=saved, weeks=weeks, changed_horizon=weeks != p.horizon_weeks)


@router.post("/protocols/{pid}/save")
def protocol_save(pid: int, name: str = Form(""), notes: str = Form(""),
                  horizon_weeks: str = Form("12"), compound_id: list[str] = Form(default=[]),
                  amount: list[str] = Form(default=[]), unit: list[str] = Form(default=[]),
                  freq_count: list[str] = Form(default=[]),
                  freq_period: list[str] = Form(default=[]), db: Session = Depends(get_db)):
    p = db.get(Protocol, pid)
    if p is None:
        raise HTTPException(404, "Protocol not found")
    refs = services.compound_refs(db)
    parsed = _parse_rows(refs, compound_id, amount, unit, freq_count, freq_period)
    if any(isinstance(e, calc.ItemResult) for e in parsed):
        return HTMLResponse('<span class="error">Fix the highlighted rows before saving.</span>')
    p.name = name.strip() or p.name
    p.notes = notes.strip()
    p.horizon_weeks = _horizon(horizon_weeks)
    p.items.clear()
    db.flush()
    for pos, i in enumerate(parsed):
        p.items.append(ProtocolItem(compound_id=i.compound_id, position=pos,
                                    amount_value=i.amount_value, amount_unit=i.amount_unit,
                                    freq_count=i.freq_count, freq_period=i.freq_period))
    db.flush()
    _revision(db, p)
    db.commit()
    return HTMLResponse(f"Saved {datetime.now():%H:%M:%S}")


@router.post("/protocols/{pid}/dates")
def set_protocol_dates(pid: int, start_date: str = Form(""), end_date: str = Form(""),
                       db: Session = Depends(get_db)):
    p = db.get(Protocol, pid)
    if p is None:
        raise HTTPException(404, "Protocol not found")
    try:
        start = date.fromisoformat(start_date) if start_date else None
        end = date.fromisoformat(end_date) if end_date else None
    except ValueError:
        raise HTTPException(400, "Enter valid ISO dates")
    if end and not start:
        raise HTTPException(400, "Set a start date before setting an end date")
    if start and end and end < start:
        raise HTTPException(400, "End date must be on or after start date")
    p.start_date, p.end_date = start, end
    _revision(db, p)
    db.commit()
    return services.flash_redirect(f"/protocols/{pid}", msg="Protocol dates saved.")


@router.post("/protocols/{pid}/active")
def toggle_active(pid: int, db: Session = Depends(get_db)):
    p = db.get(Protocol, pid)
    if p is None:
        raise HTTPException(404, "Protocol not found")
    p.is_active = not p.is_active
    _revision(db, p)
    db.commit()
    return services.flash_redirect(f"/protocols/{pid}", msg="Protocol status updated.")


@router.post("/protocols/{pid}/duplicate")
def protocol_duplicate(pid: int, db: Session = Depends(get_db)):
    p = db.get(Protocol, pid)
    if p is None:
        raise HTTPException(404, "Protocol not found")
    copy = Protocol(name=f"{p.name} (copy)", is_active=False, notes=p.notes, horizon_weeks=p.horizon_weeks, start_date=None, end_date=None)
    for i in p.items:
        copy.items.append(ProtocolItem(compound_id=i.compound_id, position=i.position,
                                       amount_value=i.amount_value, amount_unit=i.amount_unit,
                                       freq_count=i.freq_count, freq_period=i.freq_period))
    db.add(copy)
    db.commit()
    return services.flash_redirect(f"/protocols/{copy.id}", msg="Duplicated. Edit freely.")


@router.post("/protocols/{pid}/delete")
def protocol_delete(pid: int, db: Session = Depends(get_db)):
    p = db.get(Protocol, pid)
    if p is not None:
        db.delete(p)
        db.commit()
    return services.flash_redirect("/protocols", msg="Protocol deleted.")


def _revision(db: Session, p: Protocol):
    """Append an immutable snapshot of the saved plan; never overwrite prior versions."""
    from sqlalchemy import func
    last = db.scalar(select(func.max(ProtocolRevision.revision)).where(ProtocolRevision.protocol_id == p.id)) or 0
    snapshot = {"name":p.name,"notes":p.notes,"is_active":p.is_active,
                "horizon_weeks":p.horizon_weeks,
                "start_date":p.start_date.isoformat() if p.start_date else None,
                "end_date":p.end_date.isoformat() if p.end_date else None,
                "items":[{"compound_id":i.compound_id,"amount_value":i.amount_value,
                          "amount_unit":i.amount_unit,"freq_count":i.freq_count,
                          "freq_period":i.freq_period,"position":i.position} for i in p.items]}
    db.add(ProtocolRevision(protocol_id=p.id,revision=last+1,snapshot_json=json.dumps(snapshot)))


@router.get('/protocols/{pid}/history')
def history(pid:int,request:Request,db:Session=Depends(get_db)):
    p=db.get(Protocol,pid)
    if not p: raise HTTPException(404)
    versions=list(db.scalars(select(ProtocolRevision).where(ProtocolRevision.protocol_id==pid).order_by(ProtocolRevision.revision.desc())))
    return render(request,'protocol_history.html',p=p,versions=[(v,json.loads(v.snapshot_json)) for v in versions])
