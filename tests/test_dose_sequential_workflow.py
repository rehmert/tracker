"""Consecutive dose-log entries and opt-in historical form prefill.

The pytest suite provisions an isolated SQLite database via conftest.py.
No live records, vials or inventory are touched by these tests.
"""
import json
import re
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal
from app.main import app
from app.models import DoseLog, Vial
from tests.test_stage17_dose_blend_integrity import seed_vials


def _submit(vial_id, token, *, amount="2", kind="dose",
            site="Abdomen lower left", when="2026-10-25T09:30"):
    return {
        "vial_id": str(vial_id),
        "amount": amount,
        "unit": "mg",
        "kind": kind,
        "site": site,
        "taken_at": when,
        "submission_token": token,
    }


def test_success_rotates_token_without_weakening_replay_guard():
    vial_id = seed_vials("Sequential-" + str(uuid4()), 1)[0]
    original = str(uuid4())
    payload = _submit(vial_id, original)
    with TestClient(app) as client:
        first = client.post("/doses", data=payload)
        assert first.status_code == 200
        event = json.loads(first.headers["HX-Trigger-After-Settle"])
        details = event["tracker:dose-saved"]
        rotated = details["submission_token"]
        assert str(UUID(rotated)) == rotated
        assert rotated != original
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}",
                            details["new_time"])
        replay = client.post("/doses", data=payload)
        assert "already recorded" in replay.text
        assert "HX-Trigger-After-Settle" not in replay.headers
        second = client.post(
            "/doses", data=_submit(vial_id, rotated, amount="1"),
        )
        assert second.status_code == 200
        token3 = json.loads(second.headers["HX-Trigger-After-Settle"])[
            "tracker:dose-saved"
        ]["submission_token"]
        assert token3 not in (rotated, original)
    with SessionLocal() as db:
        assert db.scalar(
            select(func.count()).select_from(DoseLog)
            .where(DoseLog.vial_id == vial_id)
        ) == 2


def test_invalid_entry_does_not_rotate_one_use_token():
    vial_id = seed_vials("SequentialInvalid-" + str(uuid4()), 1)[0]
    with TestClient(app) as client:
        rejected = client.post(
            "/doses", data=_submit(vial_id, str(uuid4()), amount="100"),
        )
    assert rejected.status_code == 200
    assert "exceeds remaining" in rejected.text
    assert "HX-Trigger-After-Settle" not in rejected.headers


def test_prepare_similar_is_review_only_and_preserves_current_time():
    vial_id = seed_vials("PrepareSimilar-" + str(uuid4()), 1)[0]
    with TestClient(app) as client:
        first = client.post(
            "/doses", data=_submit(vial_id, str(uuid4())),
        )
        assert first.status_code == 200
        with SessionLocal() as db:
            did = db.scalar(
                select(DoseLog.id).where(DoseLog.vial_id == vial_id)
            )
        page = client.get(f"/doses?repeat_from={did}")
        assert page.status_code == 200
        assert "Previous recorded details loaded for review only" in page.text
        assert f'value="{vial_id}"' in page.text
        assert 'name="amount" step="any" min="0" value="2' in page.text
        assert '<option value="Abdomen lower left" selected>' in page.text
        timestamps = re.findall(
            r'<input type="datetime-local" name="taken_at" value="([^"]*)"',
            page.text,
        )
        assert timestamps and "2026-10-25T09:30" not in timestamps
        assert "Prepare similar" in client.get("/doses").text
    with SessionLocal() as db:
        assert db.scalar(
            select(func.count()).select_from(DoseLog)
            .where(DoseLog.vial_id == vial_id)
        ) == 1


def test_prepare_similar_refuses_unavailable_vial():
    vial_id = seed_vials("PrepareUnavailable-" + str(uuid4()), 1)[0]
    with TestClient(app) as client:
        client.post("/doses", data=_submit(vial_id, str(uuid4())))
        with SessionLocal() as db:
            did = db.scalar(
                select(DoseLog.id).where(DoseLog.vial_id == vial_id)
            )
            vial = db.get(Vial, vial_id)
            vial.status = "discarded"
            db.commit()
        page = client.get(f"/doses?repeat_from={did}")
    assert "historical vial is no longer available" in page.text
    assert 'name="amount" step="any" min="0" value="0"' in page.text


def test_prepare_similar_refuses_overdraw_when_stock_lower():
    vial_id = seed_vials("PrepareLowStock-" + str(uuid4()), 1)[0]
    with TestClient(app) as client:
        client.post(
            "/doses", data=_submit(vial_id, str(uuid4()), amount="6"),
        )
        with SessionLocal() as db:
            did = db.scalar(
                select(DoseLog.id).where(DoseLog.vial_id == vial_id)
            )
        page = client.get(f"/doses?repeat_from={did}")
    assert "Previous amount does not fit" in page.text
    assert 'name="amount" step="any" min="0" value="0"' in page.text


def test_historical_waste_is_not_a_reusable_dose():
    vial_id = seed_vials("PrepareWaste-" + str(uuid4()), 1)[0]
    with TestClient(app) as client:
        first = client.post(
            "/doses", data=_submit(vial_id, str(uuid4()), amount="1", kind="waste"),
        )
        assert first.status_code == 200
        with SessionLocal() as db:
            did = db.scalar(
                select(DoseLog.id).where(DoseLog.vial_id == vial_id)
            )
        assert "Prepare similar" not in client.get("/doses").text
        page = client.get(f"/doses?repeat_from={did}")
    assert "unavailable for prefill" in page.text


def test_calendar_planning_context_cannot_be_overridden_by_history():
    vial_id = seed_vials("PlannedPriority-" + str(uuid4()), 1)[0]
    with TestClient(app) as client:
        client.post("/doses", data=_submit(vial_id, str(uuid4())))
        with SessionLocal() as db:
            did = db.scalar(
                select(DoseLog.id).where(DoseLog.vial_id == vial_id)
            )
        page = client.get(
            f"/doses?repeat_from={did}&planned_date=2026-11-08"
            "&planned_amount=3&planned_unit=mg"
        )
    assert 'name="amount" step="any" min="0" value="3' in page.text
    assert "Previous recorded details loaded" not in page.text


def test_client_listens_after_settle_and_does_not_auto_submit():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/js/tracker-dose-sequential-20261102.js").read_text()
    template = (root / "app/templates/doses.html").read_text()
    assert "tracker:dose-saved" in js
    assert "token.defaultValue = data.submission_token" in js
    assert "time.defaultValue = data.new_time" in js
    assert "amount.defaultValue = '0'" in js
    assert "form.submit()" not in js
    assert "tracker-dose-sequential-20261102.js" in template
    assert "HX-Trigger-After-Settle" in template
