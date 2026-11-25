"""Calendar quick dose: synthetic stock, two editable inputs, atomic recording."""
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.main import app
from app.migrations import migrate
from app.models import Compound, Protocol, ProtocolItem, Vial, DoseLog, Blend, BlendComponent, BlendDose
from app.services import vial_views
from app.routers.calendar import _month_events


def seed(*, mixed=False, mismatch=False):
    migrate(engine)
    Base.metadata.create_all(engine)
    day = date.today() - timedelta(days=1)
    tag = uuid4().hex
    with SessionLocal() as db:
        p = Protocol(name="QA786 " + tag, is_active=True, start_date=day, end_date=day)
        db.add(p)
        db.flush()
        items, vials = [], []
        for n in range(2 if mixed else 1):
            c = Compound(name=f"QA786-{tag}-{n}", primary_unit="mg")
            db.add(c)
            db.flush()
            item = ProtocolItem(protocol_id=p.id, compound_id=c.id,
                                amount_value=3 if mismatch and n else n + 1,
                                amount_unit="mg", freq_count=1, freq_period="day", dose_time="07:00")
            vial = Vial(compound_id=c.id, label="QA786 source", status="finished" if mixed else "in_use",
                        content_value=10 * (n + 1), content_unit="mg", volume_ml=2, form="liquid")
            db.add_all([item, vial])
            db.flush()
            items.append(item.id)
            vials.append(vial.id)
        bid = None
        if mixed:
            blend = Blend(label="QA786 blend", final_volume_ml=2, status="in_use",
                          created_at=datetime.combine(day, datetime.min.time()))
            db.add(blend)
            db.flush()
            bid = blend.id
            for n, vid in enumerate(vials):
                v = db.get(Vial, vid)
                db.add(BlendComponent(blend_id=bid, compound_id=v.compound_id,
                                      source_vial_id=vid, transferred_base=10000*(n+1),
                                      transferred_ml=1, target_dose_base=1000*(n+1), target_unit="mg"))
        db.commit()
        return day, items, vials, bid


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = {}
        self.editable = []
        self.inside = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self.inside = a.get("hx-post") == "/doses"
        if not self.inside or not a.get("name"):
            return
        if tag == "input" and a.get("type") == "hidden":
            self.hidden[a["name"]] = a.get("value", "")
        elif tag in ("input", "select", "textarea"):
            self.editable.append(a["name"])

    def handle_endtag(self, tag):
        if tag == "form":
            self.inside = False


def open_form(client, day, iid):
    path = f"/calendar/log-dose?protocol_item_id={iid}&scheduled_on={day}"
    page = client.get(path)
    assert page.status_code == 200
    parsed = FormParser()
    parsed.feed(page.text)
    assert parsed.editable == ["calendar_clock", "site"]
    header = {"HX-Request": "true", "X-Tracker-CSRF": client.cookies["tracker_csrf_v1"]}
    return parsed.hidden, header


def test_786_vial_quick_entry_and_replay():
    day, items, vials, _ = seed()
    with TestClient(app) as client:
        calendar = client.get(f"/calendar?month={day:%Y-%m}")
        assert f"/calendar/log-dose?protocol_item_id={items[0]}&amp;scheduled_on={day}" in calendar.text
        form, headers = open_form(client, day, items[0])
        assert form["vial_id"] == str(vials[0])
        form.update(calendar_clock="0815", site="Abdomen lower right")
        rejected = client.post("/doses", data=dict(form, amount="2"), headers=headers)
        assert "changes to time and injection site only" in rejected.text
        result = client.post("/doses", data=form, headers=headers)
        assert result.headers.get("HX-Redirect") == f"/calendar?month={day:%Y-%m}#calendar-day-{day}"
        retry = client.post("/doses", data=form, headers=headers)
        assert not retry.headers.get("HX-Redirect")
        manual = client.get("/doses")
        assert 'name="use_remaining"' in manual.text
    with SessionLocal() as db:
        rows = list(db.scalars(select(DoseLog).where(DoseLog.vial_id == vials[0])))
        assert len(rows) == 1
        assert rows[0].amount_base == 1000
        assert rows[0].taken_at == datetime.combine(day, datetime.strptime("08:15", "%H:%M").time())
        assert rows[0].site == "Abdomen lower right"
        assert vial_views(db, [db.get(Vial, vials[0])])[vials[0]].remaining_base == 9000


def test_786_mixed_blend_one_draw_matches_both_calendar_entries():
    day, items, vials, bid = seed(mixed=True)
    with TestClient(app) as client:
        form, headers = open_form(client, day, items[0])
        assert form["vial_id"] == f"blend:{bid}"
        assert float(form["amount"]) == .2 and form["unit"] == "mL"
        result = client.post("/doses", data=dict(form, calendar_clock="07:20", site=""), headers=headers)
        assert result.headers.get("HX-Redirect")
        page = client.get(f"/calendar/log-dose?protocol_item_id={items[1]}&scheduled_on={day}")
        assert "already recorded" in page.text
    with SessionLocal() as db:
        rows = list(db.scalars(select(BlendDose).where(BlendDose.blend_id == bid)))
        assert len(rows) == 1 and abs(rows[0].volume_ml - .2) < 1e-9
        assert not list(db.scalars(select(DoseLog).where(DoseLog.vial_id.in_(vials))))
        _, _, entries, _ = _month_events(day.replace(day=1), db)
        assert all(e["status"] == "recorded" for e in entries[day] if e.get("protocol_item_id") in items)


def test_786_ambiguous_or_changed_inventory_fails_closed():
    day, items, vials, _ = seed()
    with TestClient(app) as client:
        form, headers = open_form(client, day, items[0])
        with SessionLocal() as db:
            v = db.get(Vial, vials[0])
            db.add(Vial(compound_id=v.compound_id, status="in_use",
                        content_value=10, content_unit="mg", volume_ml=2, form="liquid"))
            db.commit()
        result = client.post("/doses", data=dict(form, calendar_clock="07:00"), headers=headers)
        assert "Schedule or inventory changed" in result.text
        page = client.get(f"/calendar/log-dose?protocol_item_id={items[0]}&scheduled_on={day}")
        assert "Multiple eligible" in page.text and "Full dose log" in page.text
        assert 'name="calendar_clock"' not in page.text
    with SessionLocal() as db:
        assert not list(db.scalars(select(DoseLog).where(DoseLog.vial_id == vials[0])))


def test_786_incompatible_blend_never_guesses_draw():
    day, items, _, bid = seed(mixed=True, mismatch=True)
    with TestClient(app) as client:
        page = client.get(f"/calendar/log-dose?protocol_item_id={items[0]}&scheduled_on={day}")
        assert "No eligible in-use vial or blend" in page.text
        assert 'name="calendar_clock"' not in page.text
    with SessionLocal() as db:
        assert not list(db.scalars(select(BlendDose).where(BlendDose.blend_id == bid)))
