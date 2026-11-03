"""Quantity/date preview and opt-in vial handoff use isolated Tracker test data."""
from datetime import date, timedelta
import html
import re
from types import SimpleNamespace as NS
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select, func

from app.db import SessionLocal
from app.main import app
from app.models import Compound, DoseLog, Protocol, ProtocolItem, Vial
from app.protocol_inventory_preview import assess_planned_vials
from app import vial_recommendation


TODAY = date(2026, 11, 2)


def event(cid=7, amount=2.5, unit="mg", when=TODAY):
    return {"compound_id": cid, "amount": amount, "unit": unit, "date": when}


def vial(id, *, cid=7, status="in_use", expires=None, bud=None,
         first=None, label=""):
    return NS(id=id, compound_id=cid, status=status, expires_on=expires,
              beyond_use_on=bud, first_punctured_on=first,
              first_dosed_on=None, label=label)


def view(*, remaining=10000, dim="mass", concentration=10000):
    return NS(remaining_base=remaining, dim=dim, conc_per_ml=concentration)


def test_quantity_match_prefers_in_use_and_returns_optional_candidate():
    a = vial(1, status="sealed", label="sealed")
    b = vial(2, status="in_use", label="in-use")
    result = assess_planned_vials(event(), [a, b],
                                  {1: view(), 2: view()})
    assert result["state"] == "candidate"
    assert result["candidate_count"] == 2
    assert result["suggested_id"] == 2
    assert result["suggested_label"] == "in-use"
    assert result["matching_count"] == 2


def test_an_empty_or_nonmatching_compound_has_no_suggestion():
    assert assess_planned_vials(event(), [], {})["state"] == "none"
    wrong = vial(9, cid=999)
    assert assess_planned_vials(event(), [wrong], {9: view()})["state"] == "none"
    empty = vial(1)
    info = assess_planned_vials(event(), [empty], {1: view(remaining=0)})
    assert info["state"] == "empty"
    assert info["suggested_id"] is None


def test_two_small_vials_are_not_misrepresented_as_one_eligible_vial():
    items = [vial(1), vial(2, status="sealed")]
    result = assess_planned_vials(
        event(amount=5), items,
        {1: view(remaining=3000), 2: view(remaining=3000)},
    )
    assert result["state"] == "insufficient"
    assert result["candidate_count"] == 0
    assert result["suggested_id"] is None


def test_future_expiration_and_bud_are_evaluated_at_planned_date():
    future = TODAY + timedelta(days=7)
    expired = vial(1, expires=TODAY + timedelta(days=2))
    beyond_use = vial(2, bud=TODAY + timedelta(days=5))
    result = assess_planned_vials(event(when=future), [expired, beyond_use],
                                  {1: view(), 2: view()})
    assert result["state"] == "dates"
    assert result["date_flagged_count"] == 2
    assert result["suggested_id"] is None
    # For a current-day plan neither date has yet been reached.
    current = assess_planned_vials(event(when=TODAY), [expired, beyond_use],
                                   {1: view(), 2: view()})
    assert current["state"] == "candidate"
    assert current["candidate_count"] == 2


def test_date_warning_does_not_block_other_eligible_vial():
    bad = vial(1, bud=TODAY)
    good = vial(2, label="still recorded current")
    result = assess_planned_vials(event(), [bad, good],
                                  {1: view(), 2: view()})
    assert result["state"] == "candidate"
    assert result["date_flagged_count"] == 1
    assert result["candidate_count"] == 1
    assert result["suggested_id"] == 2


def test_missing_volume_concentration_or_incompatible_units_is_not_guessed():
    item = vial(1)
    assert assess_planned_vials(
        event(amount=0.2, unit="mL"), [item],
        {1: view(concentration=None)},
    )["state"] == "units"
    assert assess_planned_vials(
        event(amount=20, unit="IU"), [item],
        {1: view(dim="mass")},
    )["state"] == "units"


def test_volume_and_iu_units_can_be_checked_when_metadata_supports_them():
    item = vial(1)
    m = assess_planned_vials(
        event(amount=0.2, unit="mL"), [item],
        {1: view(remaining=1000, concentration=4000)},
    )
    assert m["state"] == "candidate"
    # An IU vial remains dimensionally separate from mg.
    result = assess_planned_vials(
        event(amount=4, unit="IU"), [item],
        {1: view(remaining=5, dim="iu", concentration=None)},
    )
    assert result["state"] == "candidate"


def test_discarded_or_finished_vials_are_never_suggested():
    items = [vial(1, status="discarded"), vial(2, status="finished")]
    result = assess_planned_vials(
        event(), items, {1: view(), 2: view()},
    )
    assert result["state"] == "none"


def _seed_planned_vial(*, start, expiry=None, bud=None):
    with SessionLocal() as db:
        compound = Compound(name="Inventory handoff " + str(uuid4()),
                            category="peptide")
        protocol = Protocol(
            name="Inventory preview " + str(uuid4()),
            is_active=True, start_date=start,
        )
        item = ProtocolItem(
            compound=compound, amount_value=2.5, amount_unit="mg",
            freq_count=7, freq_period="interval",
            start_week=1, position=0, dose_time="09:30",
        )
        protocol.items.append(item)
        physical = Vial(
            compound=compound, label="Recorded vial candidate",
            content_value=10, content_unit="mg", volume_ml=1,
            status="in_use", expires_on=expiry, beyond_use_on=bud,
        )
        db.add_all([protocol, physical])
        db.commit()
        return compound.id, physical.id


def _hrefs_for(url_prefix, body):
    links = re.findall(r'href="([^"]+)"', body)
    return [html.unescape(value) for value in links
            if html.unescape(value).startswith(url_prefix)]


def test_protocol_index_suggested_vial_prefills_existing_dose_form():
    planned = date.today() + timedelta(days=1)
    with TestClient(app) as client:
        cid, vid = _seed_planned_vial(start=planned)
        index = client.get("/protocols")
        assert index.status_code == 200
        assert "Inventory:" in index.text
        urls = _hrefs_for("/doses?", index.text)
        selected = []
        for url in urls:
            query = parse_qs(urlsplit(url).query)
            if query.get("vial_id") == [str(vid)]:
                selected.append((url, query))
        assert len(selected) == 1
        target, query = selected[0]
        assert query["compound_id"] == [str(cid)]
        assert query["planned_date"] == [planned.isoformat()]
        assert query["planned_time"] == ["09:30"]
        assert query["planned_amount"] == ["2.5"]
        assert query["planned_unit"] == ["mg"]
        page = client.get(target)
        assert page.status_code == 200
        assert re.search(r'<option\b[^>]*value="' + str(vid) +
                         r'"[^>]*\bselected\b', page.text)
        # A GET prefill cannot write an administration.
        with SessionLocal() as db:
            assert db.scalar(select(func.count()).select_from(DoseLog)
                             .where(DoseLog.vial_id == vid)) == 0


def test_future_expired_vial_is_not_linked_as_suggested():
    planned = date.today() + timedelta(days=7)
    with TestClient(app) as client:
        cid, vid = _seed_planned_vial(
            start=planned, expiry=date.today() + timedelta(days=1),
        )
        page = client.get("/protocols")
    assert page.status_code == 200
    assert "Quantity exists, but matching vials have recorded date warnings" in page.text
    for url in _hrefs_for("/doses?", page.text):
        assert parse_qs(urlsplit(url).query).get("vial_id") != [str(vid)]
    assert any(parse_qs(urlsplit(url).query).get("compound_id") == [str(cid)]
               for url in _hrefs_for("/dose-workspace?", page.text))


def test_workspace_uses_planned_day_for_recorded_date_warnings(monkeypatch):
    planned = date.today() + timedelta(days=6)
    with TestClient(app) as client:
        cid, vid = _seed_planned_vial(start=planned)
        seen = []
        original = vial_recommendation.rank_vials

        def observe(*args, **kwargs):
            seen.append(kwargs.get("today"))
            return original(*args, **kwargs)

        monkeypatch.setattr(vial_recommendation, "rank_vials", observe)
        response = client.get(
            f"/dose-workspace?compound_id={cid}"
            f"&planned_date={planned.isoformat()}"
            "&planned_amount=2.5&planned_unit=mg",
        )
        assert response.status_code == 200
        assert seen and seen[-1] == planned

        current = client.get(
            f"/dose-workspace?compound_id={cid}"
            "&planned_amount=2.5&planned_unit=mg",
        )
        assert current.status_code == 200
        assert seen[-1] == date.today()


def test_display_contract_remains_read_only_and_calendar_context_preserved():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    index = (root / "app/templates/protocols.html").read_text()
    js = (root / "app/static/js/tracker-protocol-dashboard-3494.js").read_text()
    assert 'data-protocol-inventory-state=' in index
    assert 'href="/dose-workspace?compound_id=' in index
    assert 'href="/doses?compound_id=' in index
    assert 'vial_id={{ r.inventory.suggested_id }}' in index
    assert "row.cells[1]?.textContent" in js
    assert "row.cells[2]?.textContent" in js
    assert "Next planned (60 days)" in index
    assert "Choose vial" in index
