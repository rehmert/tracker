"""Release 713: concise blend timeline and universal 24-hour entry contracts.

Only disposable QA data is used; never access installed DEV/PROD inventory.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import re
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.main import app
from app.migrations import migrate
from app.models import Blend, BlendComponent, BlendDose, Compound, Vial

ROOT = Path(__file__).resolve().parents[1]


def test_713_timeline_displays_only_recorded_blend_units():
    migrate(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        unique = uuid4().hex[:10]
        compound = Compound(name="QA713-Blend-" + unique, primary_unit="mg")
        db.add(compound)
        db.flush()
        vial = Vial(compound_id=compound.id, content_value=10,
                    content_unit="mg", volume_ml=2, status="finished")
        db.add(vial)
        db.flush()
        blend = Blend(label="QA713 prepared " + unique,
                      final_volume_ml=2, diluent_ml=0,
                      capacity_ml=3, status="in_use")
        db.add(blend)
        db.flush()
        db.add(BlendComponent(
            blend_id=blend.id, source_vial_id=vial.id,
            compound_id=compound.id, transferred_base=10000,
            transferred_ml=2, target_dose_base=1000,
            target_unit="mg",
        ))
        db.flush()
        draw = BlendDose(
            blend_id=blend.id, taken_at=datetime(2026, 11, 20, 13, 35),
            volume_ml=0.1, entered_value=10, entered_unit="units",
            kind="dose", site="Abdomen lower left",
            notes="QA713 test only",
        )
        db.add(draw)
        db.commit()
        bid, did = blend.id, draw.id

    with TestClient(app) as client:
        page = client.get("/doses")
        assert page.status_code == 200
        pattern = (r'<tr[^>]+data-timeline-source="blend"[^>]*'
                   + r'data-physical-source="blend:' + str(bid)
                   + r'".*?</tr>')
        matched = re.search(pattern, page.text, flags=re.S)
        assert matched is not None
        row = matched.group(0)
        assert re.search(r"<td>\s*10 units\s*</td>", row), row
        assert "mL withdrawn" not in row
        assert "0.1 mL" not in row
        assert "Abdomen lower left" not in row.split('<td>')[5]
        # Detailed inventory accounting remains available on the lower view.
        assert 'data-blend-dose-id="' + str(did) + '"' in page.text

    with SessionLocal() as db:
        same = db.get(BlendDose, did)
        assert same.volume_ml == 0.1
        assert same.entered_value == 10
        assert same.entered_unit == "units"


def test_713_global_time_assets_and_all_native_time_fields_are_covered():
    base = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")
    assert base.count("tracker-time24-global713.js?v=713") == 1
    assert base.count("tracker-time24-global713.css?v=713") == 1
    assert base.count("<html lang=\"en\">") == 1

    script = (ROOT / "app/static/js/tracker-time24-global713.js").read_text()
    for phrase in (
        'input[type="datetime-local"], input[type="time"]',
        "clock.placeholder = 'HH:MM'",
        "clock.pattern =",
        "original.hidden = true",
        "original.required = false",
        "new MutationObserver(",
        "original.dispatchEvent(new Event('change'",
        "form.addEventListener('reset'",
    ):
        assert phrase in script, phrase

    templates = ROOT / "app/templates"
    time_templates = []
    for page in templates.glob("*.html"):
        source = page.read_text(encoding="utf-8")
        if re.search(r'type=["\x27](?:datetime-local|time)["\x27]', source):
            time_templates.append(page.name)
            # Full pages extend base; _protocol_row is a partial rendered
            # inside /protocols which also extends base.
            if page.name != "_protocol_row.html":
                assert '{% extends "base.html" %}' in source, page.name
    assert {
        "doses.html", "dose_edit.html", "blend_dose_edit711.html",
        "vitals.html", "vitals_edit.html", "mobile_today509.html",
        "regimen635.html", "pk.html", "workout_backfill658.html",
        "preparation_edit.html", "_protocol_row.html",
    }.issubset(set(time_templates))


def test_713_existing_24_hour_adapter_and_native_timestamp_contract_retained():
    doses = (ROOT / "app/templates/doses.html").read_text()
    assert 'name="taken_at"' in doses
    assert 'type="datetime-local"' in doses
    assert 'tracker-time24-371.js?v=371' in doses
    assert 'data-timeline-source="blend"' in doses
    assert "{{ r.draw.entered_unit or 'mL' }}" in doses
    assert '{{ r.draw.volume_ml|num }} mL withdrawn' not in doses

    # Original values remain named for existing CSRF, HTMX, JavaScript and
    # server datetime parsers; visible HH:MM proxy itself has no name.
    script = (ROOT / "app/static/js/tracker-time24-global713.js").read_text()
    assert "clock.name =" not in script
    assert "date.name =" not in script
    assert "original.value = next" in script
    assert "clockPattern.test(clock.value)" in script
    assert "original.dataset.tracker24hEnhanced = 'true'" in script
