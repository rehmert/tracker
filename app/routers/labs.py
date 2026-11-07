import csv
import io
import math

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import charts, config, labs, services
from ..attachment_integrity337 import uploaded_transaction, delete_after_commit
from ..scoped_db390 import get_scoped_db390
from ..models import LabReport, LabResult
from ..templating import render

from ..attachment_scope396 import require_attachment_scope396
from ..attachment_files400 import (
    require_attachment_workspace400,
    attachment_directory400,
    attachment_file400,
)

router = APIRouter(
    dependencies=[
        Depends(require_attachment_scope396),
        Depends(require_attachment_workspace400),
    ]
)
RANGES = {365: "1 year", 1095: "3 years", 3650: "All"}
BLANK_ROW = {"analyte": "", "value": "", "unit": "", "ref_low": "", "ref_high": ""}


def _groups(db: Session) -> dict[str, list[tuple[LabResult, LabReport]]]:
    rows = db.execute(select(LabResult, LabReport).join(LabReport, LabResult.report_id == LabReport.id)).all()
    groups: dict[str, list[tuple[LabResult, LabReport]]] = {}
    for res, rep in rows:
        groups.setdefault(labs.analyte_key(res.analyte), []).append((res, rep))
    return groups


def _points(items) -> list[labs.Point]:
    return [labs.Point(rep.drawn_on, res.value, res.unit, res.ref_low, res.ref_high)
            for res, rep in items]


def _name_options(db: Session) -> list[str]:
    seen = {n.lower(): n for n in labs.COMMON_ANALYTES}
    for (name,) in db.execute(select(LabResult.analyte).distinct()).all():
        seen.setdefault(name.lower(), name)
    return sorted(seen.values(), key=str.lower)


@router.get("/labs")
def labs_index(request: Request, db: Session = Depends(get_scoped_db390)):
    cards = []
    for key, items in _groups(db).items():
        res, rep = max(items, key=lambda it: (it[1].drawn_on, it[0].id))
        sr = labs.build_series(res.analyte, _points(items))
        svg = charts.line_chart(
            [charts.Series(res.analyte, sr.points, fmt="{:.8f}")], width=420, plot_h=90,
            unit=f" {sr.unit}", band=sr.band, band_label="Range printed on the latest report")
        cards.append({"key": key, "name": res.analyte, "res": res, "rep": rep, "n": len(items),
                      "svg": svg, "skipped": sr.skipped, "unit": sr.unit,
                      "status": labs.range_status(res.value, res.ref_low, res.ref_high)})
    cards.sort(key=lambda c: (c["name"].casefold(), c["key"]))
    reports = list(db.scalars(select(LabReport).order_by(LabReport.drawn_on.desc(), LabReport.id.desc())))
    return render(request, "labs.html", cards=cards, reports=reports)


def _form(request: Request, db: Session, rows=None, values=None, error=None, copied_from=None):
    # The chooser is read-only and capped for a compact page.
    # Keep the query here so it is available on initial
    # creation and on form re-render after validation errors.
    source_reports = list(db.scalars(
        select(LabReport)
        .order_by(LabReport.drawn_on.desc(), LabReport.id.desc())
        .limit(50)
    ))
    return render(request, "lab_form.html", rows=rows or [dict(BLANK_ROW) for _ in range(3)],
                  v=values or {"drawn_on": date.today().isoformat(), "lab_name": "", "notes": ""},
                  names=_name_options(db), copied_from=copied_from, source_reports=source_reports,
                  err=error or request.query_params.get("err"))


@router.get('/labs/compare')
def compare_reports(request: Request, first_id: int | None = None, second_id: int | None = None,
                    db: Session = Depends(get_scoped_db390)):
    reports = list(db.scalars(select(LabReport).order_by(LabReport.drawn_on.desc(), LabReport.id.desc())))
    left = db.get(LabReport, first_id) if first_id else None
    right = db.get(LabReport, second_id) if second_id else None
    if left is None and reports: left = reports[0]
    if right is None and len(reports) > 1: right = reports[1]
    def indexed(report):
        return {labs.analyte_key(r.analyte): r for r in report.results} if report else {}
    a, b = indexed(left), indexed(right)
    rows = []
    for key in sorted(set(a) | set(b)):
        newer, older = a.get(key), b.get(key)
        converted = labs.convert(key, older.value, older.unit, newer.unit) if newer and older else None
        delta = newer.value - converted if newer and converted is not None else None
        rows.append({'name': (newer or older).analyte, 'newer': newer, 'older': older,
                     'converted': converted, 'delta': delta, 'comparable': delta is not None})
    return render(request, 'lab_compare.html', reports=reports, left=left, right=right, rows=rows)


@router.get("/labs/new")
def new_report(request: Request, copy_from: int | None = None,
               db: Session = Depends(get_scoped_db390)):
    if copy_from is None:
        return _form(request, db)

    previous = db.get(LabReport, copy_from)
    if previous is None:
        raise HTTPException(404, "Source lab report not found")

    # Copy names and units only. Never reuse measurements,
    # reference ranges, dates, notes, or uploaded files.
    rows = [
        dict(
            analyte=result.analyte,
            value="",
            unit=result.unit,
            ref_low="",
            ref_high="",
        )
        for result in previous.results
    ]

    return _form(
        request,
        db,
        rows=rows or None,
        copied_from=previous,
    )


@router.get("/labs/row")
def blank_row(request: Request, db: Session = Depends(get_scoped_db390)):
    return render(request, "_lab_row.html", row=dict(BLANK_ROW))


def _opt_float(text: str) -> float | None:
    text = (text or "").strip()
    return float(text) if text else None


def _parse_rows(analyte, value, unit, ref_low, ref_high):
    """Returns (LabResult list, echo rows for re-rendering, error or None)."""
    echo = [dict(analyte=a, value=v, unit=u, ref_low=lo, ref_high=hi)
            for a, v, u, lo, hi in zip(analyte, value, unit, ref_low, ref_high)]
    results = []
    for r in echo:
        if not r["analyte"].strip() and not r["value"].strip():
            continue                                    # blank row
        try:
            if not r["analyte"].strip():
                raise ValueError("Every result needs an analyte name.")
            if not r["unit"].strip():
                raise ValueError(f"'{r['analyte'].strip()}' needs a unit (as printed on the report).")
            val = float(r["value"])
            lo, hi = _opt_float(r["ref_low"]), _opt_float(r["ref_high"])
            if (lo is None) != (hi is None):
                raise ValueError(f"'{r['analyte'].strip()}': enter both ends of the printed range, or neither.")
            if lo is not None and lo > hi:
                raise ValueError(f"'{r['analyte'].strip()}': the printed range's low end is above its high end.")
        except ValueError as exc:
            msg = str(exc)
            if msg.startswith("could not convert"):
                msg = f"'{r['value'] or r['analyte']}' isn't a valid number."
            return [], echo, msg
        results.append(LabResult(analyte=r["analyte"].strip()[:120], value=val,
                                 unit=r["unit"].strip()[:30], ref_low=lo, ref_high=hi))
    if not results:
        return [], echo, "Add at least one result."
    return results, echo, None


CSV_MAX_BYTES = 2 * 1024 * 1024
CSV_MAX_ROWS = 2000
CSV_HEADERS = {
    "analyte": {"analyte", "test", "test name", "analyte name", "name"},
    "value": {"value", "result", "result value"},
    "unit": {"unit", "units"},
    "ref_low": {"ref low", "ref_low", "reference low", "range low", "low"},
    "ref_high": {"ref high", "ref_high", "reference high", "range high", "high"},
    "note": {"note", "notes", "comment", "comments"},
}


def _parse_csv_data(data: bytes):
    """Parse a complete CSV before writing anything to the database."""
    if not data or len(data) > CSV_MAX_BYTES:
        raise ValueError("CSV must be nonempty and no larger than 2 MB.")
    try:
        content = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded.") from exc
    try:
        reader = csv.DictReader(io.StringIO(content, newline=""), strict=True)
        if not reader.fieldnames:
            raise ValueError("CSV needs a header row.")
        normalized = [h.strip().lower().replace("-", " ") for h in reader.fieldnames]
        mapping = {}
        for canonical, aliases in CSV_HEADERS.items():
            matches = [reader.fieldnames[i] for i, h in enumerate(normalized) if h in aliases]
            if len(matches) > 1:
                raise ValueError(f"CSV has duplicate {canonical} columns.")
            if matches:
                mapping[canonical] = matches[0]
        if any(k not in mapping for k in ("analyte", "value", "unit")):
            raise ValueError("CSV requires analyte, value, and unit columns.")
        rows = []
        for line, record in enumerate(reader, start=2):
            if len(rows) >= CSV_MAX_ROWS:
                raise ValueError("CSV exceeds the 2,000-result limit.")
            if None in record:
                raise ValueError(f"CSV row {line} has more columns than its header.")
            row = {key: (record.get(header) or "").strip() for key, header in mapping.items()}
            if not any(row.values()):
                continue
            parsed, _, error = _parse_rows([row.get("analyte", "")], [row.get("value", "")],
                                            [row.get("unit", "")], [row.get("ref_low", "")],
                                            [row.get("ref_high", "")])
            if error:
                raise ValueError(f"CSV row {line}: {error}")
            if not math.isfinite(parsed[0].value) or any(
                x is not None and not math.isfinite(x) for x in (parsed[0].ref_low, parsed[0].ref_high)
            ):
                raise ValueError(f"CSV row {line}: values must be finite numbers.")
            if len(row.get("analyte", "")) > 120 or len(row.get("unit", "")) > 30 or len(row.get("note", "")) > 300:
                raise ValueError(f"CSV row {line}: a text field exceeds its maximum length.")
            parsed[0].note = row.get("note", "")
            rows.extend(parsed)
    except csv.Error as exc:
        raise ValueError(f"Malformed CSV: {exc}") from exc
    if not rows:
        raise ValueError("CSV contains no analyte results.")
    return rows


async def _read_csv_upload(file: UploadFile):
    if not (file.filename or "").lower().endswith(".csv"):
        raise ValueError("Select a .csv file.")
    data = await file.read(CSV_MAX_BYTES + 1)
    return _parse_csv_data(data)


@router.get("/labs/csv-template")
def csv_template():
    from fastapi.responses import Response
    sample = "analyte,value,unit,ref_low,ref_high,note\nTSH,1.25,mIU/L,0.45,4.5,\nIGF-1,180,ng/mL,80,250,\n"
    return Response(sample, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="lab-analytes-template.csv"'})


@router.post("/labs/import-csv")
async def import_new_csv(request: Request, csv_file: UploadFile = File(...),
                         drawn_on: str = Form(""), lab_name: str = Form(""),
                         notes: str = Form(""), db: Session = Depends(get_scoped_db390)):
    values = {"drawn_on": drawn_on, "lab_name": lab_name, "notes": notes}
    try:
        when = services.parse_date(drawn_on)
        if when is None:
            raise ValueError("Select a draw date.")
        results = await _read_csv_upload(csv_file)
    except ValueError as exc:
        return _form(request, db, values=values, error=str(exc))
    report = LabReport(drawn_on=when, lab_name=lab_name.strip()[:160], notes=notes.strip())
    report.results = results
    db.add(report)
    db.commit()
    return services.flash_redirect(f"/labs/{report.id}", msg=f"Imported {len(results)} results from CSV.")


@router.post("/labs/{rid}/import-csv")
async def import_existing_csv(rid: int, csv_file: UploadFile = File(...),
                              db: Session = Depends(get_scoped_db390)):
    rep = _report(db, rid)
    try:
        results = await _read_csv_upload(csv_file)
    except ValueError as exc:
        return services.flash_redirect(f"/labs/{rid}", err=str(exc))
    rep.results.extend(results)
    db.commit()
    return services.flash_redirect(f"/labs/{rid}", msg=f"Imported {len(results)} results from CSV.")


@router.post("/labs")
async def create_report(request: Request, drawn_on: str = Form(""), lab_name: str = Form(""),
                        notes: str = Form(""), analyte: list[str] = Form(default=[]),
                        value: list[str] = Form(default=[]), unit: list[str] = Form(default=[]),
                        ref_low: list[str] = Form(default=[]), ref_high: list[str] = Form(default=[]),
                        file: UploadFile | None = File(None), db: Session = Depends(get_scoped_db390)):
    values = {"drawn_on": drawn_on, "lab_name": lab_name, "notes": notes}
    results, echo, error = _parse_rows(analyte, value, unit, ref_low, ref_high)
    when = None
    if not error:
        try:
            when = services.parse_date(drawn_on) or date.today()
        except ValueError:
            error = "Enter the draw date as a valid date."
    stored = {}
    if not error and file is not None and file.filename:
        try:
            stored = await services.save_upload(file, attachment_directory400("labs"))
        except ValueError as exc:
            error = str(exc)
    if error:
        return _form(request, db, rows=echo or None, values=values, error=error)
    with uploaded_transaction(db, stored, attachment_directory400("labs"), services.delete_stored_file):
        report = LabReport(drawn_on=when, lab_name=lab_name.strip(), notes=notes.strip(), **stored)
        report.results = results
        db.add(report)
        db.commit()
    return services.flash_redirect(f"/labs/{report.id}", msg=f"Saved {len(results)} result(s).")


@router.get("/labs/analyte")
def analyte_page(request: Request, name: str, days: int = 3650, events: int = 1,
                 db: Session = Depends(get_scoped_db390)):
    items = _groups(db).get(labs.analyte_key(name))
    if not items:
        raise HTTPException(404, "No results for that analyte")
    days = days if days in RANGES else 3650
    items.sort(key=lambda it: (it[1].drawn_on, it[0].id), reverse=True)
    latest = items[0][0]
    sr = labs.build_series(latest.analyte, _points(items))
    now = datetime.now()
    first = min(labs.at_noon(rep.drawn_on) for _, rep in items)
    start = now - timedelta(days=days) if days < 3650 else first - timedelta(days=2)
    pts = [(t, v) for t, v in sr.points if t >= start]
    ev = services.events_between(db, start, now) if events else []
    svg = charts.line_chart([charts.Series(latest.analyte, pts, fmt="{:.8f}")], unit=f" {sr.unit}",
                            x_range=(start, now), events=ev, band=sr.band,
                            band_label="Range printed on the latest report")
    rows = []
    for res, rep in items:
        rows.append({"res": res, "rep": rep, "status": labs.range_status(res.value, res.ref_low, res.ref_high),
                     "converted": labs.convert(res.analyte, res.value, res.unit, sr.unit)})
    return render(request, "lab_analyte.html", name=latest.analyte, rows=rows, svg=svg, unit=sr.unit,
                  skipped=sr.skipped, days=days, ranges=RANGES, events_on=bool(events),
                  key=labs.analyte_key(name))


def _report(db: Session, rid: int) -> LabReport:
    r = db.get(LabReport, rid)
    if r is None:
        raise HTTPException(404, "Report not found")
    return r



def _lab_csv_text(value):
    """Protect spreadsheet software from formulas in text fields."""
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    if text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def _lab_csv_response(rows, filename: str):
    """UTF-8 CSV with BOM and CRLF line endings."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerows(rows)
    return Response(
        content=buffer.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/labs/{rid}/export.csv")
def export_lab_report_csv(rid: int, db: Session = Depends(get_scoped_db390)):
    """Download original recorded measurements without display rounding."""
    report = _report(db, rid)
    rows = [[
        "drawn_on", "lab_name", "analyte", "value",
        "unit", "ref_low", "ref_high", "note",
    ]]

    for result in report.results:
        rows.append([
            report.drawn_on.isoformat(),
            _lab_csv_text(report.lab_name),
            _lab_csv_text(result.analyte),
            result.value,
            _lab_csv_text(result.unit),
            "" if result.ref_low is None else result.ref_low,
            "" if result.ref_high is None else result.ref_high,
            _lab_csv_text(result.note),
        ])

    return _lab_csv_response(
        rows, f"lab-report-{rid}-results.csv"
    )


@router.get("/labs/{rid}/template.csv")
def lab_report_template_csv(rid: int, db: Session = Depends(get_scoped_db390)):
    """Blank template with names and units but no previous results."""
    report = _report(db, rid)
    rows = [[
        "analyte", "value", "unit",
        "ref_low", "ref_high", "note",
    ]]

    for result in report.results:
        rows.append([
            _lab_csv_text(result.analyte),
            "",
            _lab_csv_text(result.unit),
            "",
            "",
            "",
        ])

    return _lab_csv_response(
        rows, f"lab-report-{rid}-blank-template.csv"
    )


REPORT_SORT_COLUMNS = ("analyte", "value", "unit", "range", "status", "note")


def _sort_report_rows(rows, sort: str, direction: str):
    """Sort report rows without changing persisted result order."""
    sort = sort if sort in REPORT_SORT_COLUMNS else "analyte"
    direction = direction if direction in ("asc", "desc") else "asc"
    def key(row):
        res = row["res"]
        status = row["status"]
        values = {
            "analyte": res.analyte.casefold(),
            "value": res.value,
            "unit": res.unit.casefold(),
            "range": (res.ref_low if res.ref_low is not None else float("inf"),
                      res.ref_high if res.ref_high is not None else float("inf")),
            "status": {"below": 0, "within": 1, "above": 2, None: 3}[status],
            "note": (res.note or "").casefold(),
        }
        return (values[sort], res.id)
    return sorted(rows, key=key, reverse=(direction == "desc"))


@router.get("/labs/{rid}")
def report_page(rid: int, request: Request, sort: str = "analyte", direction: str = "asc",
                db: Session = Depends(get_scoped_db390)):
    rep = _report(db, rid)
    rows = [{"res": r, "status": labs.range_status(r.value, r.ref_low, r.ref_high)} for r in rep.results]
    sort = sort if sort in REPORT_SORT_COLUMNS else "analyte"
    direction = direction if direction in ("asc", "desc") else "asc"
    return render(request, "lab_report.html", rep=rep, rows=_sort_report_rows(rows, sort, direction),
                  names=_name_options(db), sort=sort, direction=direction)


@router.get("/labs/{rid}/file")
def report_file(rid: int, db: Session = Depends(get_scoped_db390)):
    rep = _report(db, rid)
    path = attachment_file400("labs", rep.stored_name) if rep.stored_name else None
    if path is None or not path.exists():
        raise HTTPException(404, "No file for this report")
    return FileResponse(path, media_type=rep.content_type, filename=rep.original_name,
                        content_disposition_type="inline",
                        headers={"X-Content-Type-Options": "nosniff"})


@router.post("/labs/{rid}/results")
def add_result(rid: int, analyte: str = Form(""), value: str = Form(""), unit: str = Form(""),
               ref_low: str = Form(""), ref_high: str = Form(""), note: str = Form(""),
               db: Session = Depends(get_scoped_db390)):
    rep = _report(db, rid)
    results, _, error = _parse_rows([analyte], [value], [unit], [ref_low], [ref_high])
    if error:
        return services.flash_redirect(f"/labs/{rid}", err=error)
    results[0].note = note.strip()[:300]
    rep.results.append(results[0])
    db.commit()
    return services.flash_redirect(f"/labs/{rid}", msg="Result added.")



# Release 482: existing report and analyte editing.
# Uses the same scoped database and attachment authorization
# dependencies as the other lab endpoints.


def _edit_report_values482(drawn_on, lab_name, notes):
    if (
        not isinstance(drawn_on, str)
        or not isinstance(lab_name, str)
        or not isinstance(notes, str)
    ):
        raise ValueError("Invalid report fields")

    try:
        when = date.fromisoformat(drawn_on.strip())
    except ValueError:
        raise ValueError("Enter a valid draw date") from None

    name = lab_name.strip()
    note = notes.strip()

    if len(name) > 160 or len(note) > 10000:
        raise ValueError("Report text exceeds allowed length")

    return when, name, note


def _edit_result_values482(
    analyte, value, unit, ref_low, ref_high, note
):
    if any(
        not isinstance(item, str)
        for item in (analyte, value, unit, ref_low, ref_high, note)
    ):
        raise ValueError("Invalid analyte fields")

    name = analyte.strip()
    units = unit.strip()
    comment = note.strip()

    if not name or len(name) > 120:
        raise ValueError("Analyte name must contain 1–120 characters")

    if not units or len(units) > 30:
        raise ValueError("Unit must contain 1–30 characters")

    if len(comment) > 300:
        raise ValueError("Analyte note exceeds 300 characters")

    try:
        measurement = float(value.strip())
        low = float(ref_low.strip()) if ref_low.strip() else None
        high = float(ref_high.strip()) if ref_high.strip() else None
    except ValueError:
        raise ValueError("Enter valid numerical values") from None

    if not math.isfinite(measurement):
        raise ValueError("Measurement must be finite")

    if (low is None) != (high is None):
        raise ValueError("Provide both reference limits or neither")

    if low is not None:
        if not math.isfinite(low) or not math.isfinite(high):
            raise ValueError("Reference limits must be finite")
        if low > high:
            raise ValueError("Reference low exceeds reference high")

    return name, measurement, units, low, high, comment


@router.post("/labs/{rid}/edit")
def edit_report482(
    rid: int,
    drawn_on: str = Form(""),
    lab_name: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    rep = _report(db, rid)

    try:
        when, name, note = _edit_report_values482(
            drawn_on, lab_name, notes
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None

    rep.drawn_on = when
    rep.lab_name = name
    rep.notes = note
    db.commit()

    # The attached report, its metadata, and every individual
    # analyte remain unchanged.
    return services.flash_redirect(
        f"/labs/{rid}", msg="Report details updated."
    )


@router.post("/lab-results/{xid}/edit")
def edit_result482(
    xid: int,
    analyte: str = Form(""),
    value: str = Form(""),
    unit: str = Form(""),
    ref_low: str = Form(""),
    ref_high: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    result = db.get(LabResult, xid)

    if result is None:
        raise HTTPException(404, "Lab result not found")

    # Ensure the result belongs to a report accessible under
    # the current database scope.
    _report(db, result.report_id)

    try:
        name, number, units, low, high, comment = (
            _edit_result_values482(
                analyte, value, unit, ref_low, ref_high, note
            )
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None

    result.analyte = name
    result.value = number
    result.unit = units
    result.ref_low = low
    result.ref_high = high
    result.note = comment

    rid = result.report_id
    db.commit()

    return services.flash_redirect(
        f"/labs/{rid}", msg="Analyte result updated."
    )


@router.post("/lab-results/{xid}/delete")
def delete_result(xid: int, db: Session = Depends(get_scoped_db390)):
    res = db.get(LabResult, xid)
    if res is None:
        raise HTTPException(404, "Result not found")
    rid = res.report_id
    db.delete(res)
    db.commit()
    return services.flash_redirect(f"/labs/{rid}", msg="Result removed.")


@router.post("/labs/{rid}/delete")
def delete_report(rid: int, db: Session = Depends(get_scoped_db390)):
    rep = _report(db, rid)
    stored_name = rep.stored_name
    db.delete(rep)
    db.commit()
    delete_after_commit(stored_name, attachment_directory400("labs"), services.delete_stored_file)
    return services.flash_redirect("/labs", msg="Report deleted.")

@router.get("/labs/trends/{analyte_key}")
def analyte_trend(analyte_key: str, request: Request, db: Session = Depends(get_scoped_db390)):
    from urllib.parse import unquote
    key = unquote(analyte_key)
    items = _groups(db).get(key)
    if not items:
        raise HTTPException(404, "Analyte not found")
    latest, _ = max(items, key=lambda item: (item[1].drawn_on, item[0].id))
    series = labs.build_series(latest.analyte, _points(items))
    chart = charts.line_chart([charts.Series(latest.analyte, series.points)], width=850,
                              unit=f" {series.unit}", band=series.band,
                              band_label="Range printed on latest report")
    rows = sorted(items, key=lambda x: x[1].drawn_on, reverse=True)
    return render(request, "lab_trend.html", title=latest.analyte, chart=chart,
                  rows=rows, unit=series.unit, skipped=series.skipped)
