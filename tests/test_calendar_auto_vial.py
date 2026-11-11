"""Calendar -> dose handoff: select a single usable in-use vial."""
import re
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import Compound, DoseLog, Vial
from app.routers.doses import _select_dose_vial


def test_selection_rules_without_db_mutations():
    def vial(number, compound, status):
        return SimpleNamespace(id=number, compound_id=compound, status=status)

    def view(remaining):
        return SimpleNamespace(remaining_base=remaining, dim="mass", conc_per_ml=10000.0)

    stock = [
        vial(1, 7, "sealed"),
        vial(2, 7, "in_use"),
        vial(3, 7, "in_use"),
        vial(4, 8, "in_use"),
    ]
    views = {1:view(10000), 2:view(1000), 3:view(10000), 4:view(10000)}

    # Oldest eligible in-use; ignore unopened and other-compound vials.
    assert _select_dose_vial(stock, views, 7, None, "2026-11-09", 2, "mg")[0] == 3

    # Explicit matching vial takes precedence, even when sealed.
    assert _select_dose_vial(stock, views, 7, 1, "2026-11-09", 2, "mg")[0] == 1

    # Mismatched explicit vial cannot silently select the wrong compound.
    chosen, warning = _select_dose_vial(stock, views, 7, 4, "2026-11-09", 2, "mg")
    assert chosen == 3
    assert "different compound" in warning

    # Unsupported units and insufficient in-use contents require manual choice.
    chosen, warning = _select_dose_vial(stock, views, 7, None, "2026-11-09", 2, "IU")
    assert chosen is None
    assert "Choose a vial manually" in warning
    assert _select_dose_vial(stock, views, 7, None, "", None, "")[0] == 2


def _seed():
    # tests/conftest isolates the DB; it deliberately does NOT create tables.
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        a = Compound(name="CalendarAuto-" + str(uuid4()), primary_unit="mg")
        b = Compound(name="CalendarOther-" + str(uuid4()), primary_unit="mg")
        db.add_all([a, b])
        db.flush()
        ids = []
        for state in ("sealed", "in_use", "in_use"):
            v = Vial(compound_id=a.id, content_value=10, content_unit="mg",
                     volume_ml=1, status=state)
            db.add(v)
            db.flush()
            ids.append(v.id)
        wrong = Vial(compound_id=b.id, content_value=10, content_unit="mg",
                     volume_ml=1, status="in_use")
        db.add(wrong)
        db.commit()
        return a.id, ids, wrong.id


def _form_selection(html):
    form = re.search(r'<select name="vial_id" required>(.*?)</select>', html, re.S)
    assert form is not None
    selected = []
    for tag in re.findall(r'<option\b[^>]*>', form.group(1)):
        if re.search(r'\bselected(?:\s|>)', tag):
            m = re.search(r'\bvalue="([^"]*)"', tag)
            selected.append(m.group(1) if m else None)
    return selected


def _url(cid, extra=""):
    return (f"/doses?compound_id={cid}&planned_date=2026-11-09"
            "&planned_time=09%3A00&planned_amount=2&planned_unit=mg" + extra)


def test_http_calendar_prefill_selects_correct_vial_and_does_not_log():
    cid, ids, wrong = _seed()
    with TestClient(app) as client:
        response = client.get(_url(cid))
        assert response.status_code == 200
        assert _form_selection(response.text) == [str(ids[1])]
        assert 'name="amount" step="any" min="0" value="2' in response.text
        assert "First eligible in-use vial selected automatically" in response.text

        manual = client.get(_url(cid, f"&vial_id={ids[2]}"))
        assert _form_selection(manual.text) == [str(ids[2])]

        mismatched = client.get(_url(cid, f"&vial_id={wrong}"))
        assert _form_selection(mismatched.text) == [str(ids[1])]
        assert "different compound" in mismatched.text

        with SessionLocal() as db:
            db.add(DoseLog(vial_id=ids[1], taken_at=datetime(2026, 11, 1),
                           entered_value=9, entered_unit="mg",
                           amount_base=9000, kind="dose"))
            db.commit()

        insufficient = client.get(_url(cid))
        assert _form_selection(insufficient.text) == [str(ids[2])]

        with SessionLocal() as db:
            for v in db.scalars(select(Vial).where(Vial.id.in_(ids[1:]))):
                v.status = "finished"
            db.commit()

        no_open = client.get(_url(cid))
        assert _form_selection(no_open.text) == [str(ids[0])]
        assert "Lowest-index eligible unopened vial" in no_open.text

        sealed = client.get(_url(cid, f"&vial_id={ids[0]}"))
        assert _form_selection(sealed.text) == [str(ids[0])]

    with SessionLocal() as db:
        assert db.scalar(
            select(func.count()).select_from(DoseLog)
            .where(DoseLog.vial_id.in_(ids))
        ) == 1  # The explicit fixture dose only.
