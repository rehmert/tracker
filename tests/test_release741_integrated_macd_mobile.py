"""Release 741 integrated MACD: Supply inventory, COA/Vial/Lab,
protocol/calendar, Notes, mobile action consistency; all testing disposable.
"""
from datetime import date
import json
from pathlib import Path
import re
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jinja2 import Environment
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models import (
    ChangeAudit, Compound, InventoryAdjustment, Page, Purchase,
    Supply, SupplyCategory, SupplyProduct, SupplyUsage,
)
from app.routers import supplies, pages

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "app/static/css/tracker-integrated-macd741.css"


@pytest.fixture
def env(tmp_path):
    engine = create_engine(
        "sqlite:///" + str(tmp_path / "integrated741.sqlite"),
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        cur = connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(supplies.router)
    app.include_router(pages.router)

    def scoped():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = scoped
    with TestClient(app, follow_redirects=False) as client:
        # Seed built-in supply categories before other writes.
        assert client.get("/supplies").status_code == 200
        yield client, Session
    engine.dispose()


def post(client, path, payload):
    return client.post(
        path, content=urlencode(payload),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )


def seed(Session, kind="needle", name="Test Needle", units=10):
    with Session() as db:
        purchase = Purchase(vendor="Test vendor", purchased_on=date(2026, 11, 21))
        compound = Compound(name="Test Compound " + name)
        db.add_all((purchase, compound))
        db.flush()
        item = Supply(
            name=name, purchase_id=purchase.id, compound_id=compound.id,
            kind=kind, purchased_qty=units, remaining_qty=units,
            unit_price_cents=245, notes="original",
        )
        db.add(item)
        db.commit()
        return item.id, purchase.id, compound.id


def version(client, supply_id):
    response = client.get("/supplies")
    assert response.status_code == 200
    html = response.text
    m = re.search(
        rf'action="/supplies/{supply_id}/edit"[^>]*>.*?'
        rf'name="version" value="([0-9a-f]{{64}})"', html, re.S,
    )
    assert m, html[-2000:]
    return m.group(1), html


def category_version(client, category_id):
    html = client.get("/supplies").text
    m = re.search(
        rf'action="/supplies/categories/{category_id}/edit"[^>]*>.*?'
        rf'name="version" value="([0-9a-f]{{64}})"', html, re.S,
    )
    assert m, html[-1800:]
    return m.group(1)


def test_741_diag_fixture_supply_list(env):
    client, _ = env
    assert client.get("/supplies").status_code == 200


def test_741_diag_seed_and_render(env):
    client, Session = env
    sid, pid, cid = seed(Session)
    assert sid > 0 and pid > 0 and cid > 0
    response = client.get("/supplies")
    assert response.status_code == 200
    assert "Test Needle" in response.text


def test_741_diag_version_form(env):
    client, Session = env
    sid, _, _ = seed(Session)
    v, html = version(client, sid)
    assert len(v) == 64 and f'action="/supplies/{sid}/edit"' in html


def test_741_diag_edit_post_response(env):
    client, Session = env
    sid, _, cid = seed(Session)
    v, _ = version(client, sid)
    response = post(client, f"/supplies/{sid}/edit", dict(
        version=v, name=" Needles box ", notes="  Cabinet A ",
        kind="needle", compound_id=str(cid),
    ))
    assert response.status_code == 303
    assert "err=" not in response.headers["location"], response.headers["location"]


def test_741_diag_edit_persisted_audit(env):
    client, Session = env
    sid, _, cid = seed(Session)
    v, _ = version(client, sid)
    response = post(client, f"/supplies/{sid}/edit", dict(
        version=v, name=" Needles box ", notes="  Cabinet A ",
        kind="needle", compound_id=str(cid),
    ))
    assert response.status_code == 303 and "err=" not in response.headers["location"]
    with Session() as db:
        record = db.get(Supply, sid)
        assert record.name == "Needles box" and record.notes == "Cabinet A"
        audit = db.scalar(select(ChangeAudit).where(
            ChangeAudit.entity_type == "supply",
            ChangeAudit.entity_id == sid, ChangeAudit.action == "edit",
        ))
        assert audit is not None and json.loads(audit.after_json)["name"] == record.name


def test_741_supply_edit_preserves_ledger_and_records_private_audit(env):
    client, Session = env
    sid, pid, cid = seed(Session)
    v, page = version(client, sid)
    assert "Edit supply" in page and "Delete supply" in page
    assert f'action="/supplies/{sid}/delete"' in page
    response = post(client, f"/supplies/{sid}/edit", dict(
        version=v, name=" Needles box ", notes="  Cabinet A ",
        kind="needle", compound_id=str(cid),
    ))
    assert response.status_code == 303
    assert "err=" not in response.headers["location"]
    with Session() as db:
        s = db.get(Supply, sid)
        assert (s.name, s.notes, s.kind, s.compound_id) == (
            "Needles box", "Cabinet A", "needle", cid
        )
        assert (s.purchase_id, s.unit_price_cents, s.purchased_qty, s.remaining_qty) == (
            pid, 245, 10, 10
        )
        a = db.scalar(select(ChangeAudit).where(
            ChangeAudit.entity_type == "supply",
            ChangeAudit.entity_id == sid, ChangeAudit.action == "edit",
        ))
        assert json.loads(a.before_json)["name"] == "Test Needle"
        assert json.loads(a.after_json)["name"] == "Needles box"


@pytest.mark.parametrize("patch", [
    {"name": ""},
    {"name": "X" * 161},
    {"notes": "n" * 2001},
    {"kind": "not_a_category"},
    {"compound_id": "0xdead"},
    {"compound_id": "999999"},
])
def test_741_bad_supply_edits_rejected_without_mutating(env, patch):
    client, Session = env
    sid, _, cid = seed(Session)
    v, _ = version(client, sid)
    request = dict(
        version=v, name="Test Needle", notes="original",
        kind="needle", compound_id=str(cid),
    )
    request.update(patch)
    denied = post(client, f"/supplies/{sid}/edit", request)
    assert denied.status_code == 303
    assert "err=" in denied.headers["location"]
    with Session() as db:
        item = db.get(Supply, sid)
        assert (item.name, item.notes, item.kind, item.compound_id) == (
            "Test Needle", "original", "needle", cid
        )


def test_741_noop_edit_has_no_audit(env):
    client, Session = env
    sid, _, cid = seed(Session)
    v, _ = version(client, sid)
    result = post(client, f"/supplies/{sid}/edit", dict(
        version=v, name="Test Needle", notes="original",
        kind="needle", compound_id=str(cid),
    ))
    assert result.status_code == 303
    with Session() as db:
        assert db.scalar(select(ChangeAudit.id).where(
            ChangeAudit.entity_type == "supply",
            ChangeAudit.entity_id == sid,
        )) is None


def test_741_unused_equivalent_category_reassignment_and_invalid_units(env):
    client, Session = env
    sid, _, cid = seed(Session)
    v, _ = version(client, sid)
    allowed = post(client, f"/supplies/{sid}/edit", dict(
        version=v, name="Test Needle", notes="original",
        kind="syringe", compound_id=str(cid),
    ))
    assert "err=" not in allowed.headers["location"]
    fresh, _ = version(client, sid)
    blocked = post(client, f"/supplies/{sid}/edit", dict(
        version=fresh, name="Test Needle", notes="original",
        kind="bac_water", compound_id=str(cid),
    ))
    assert "err=" in blocked.headers["location"]
    with Session() as db:
        assert db.get(Supply, sid).kind == "syringe"


@pytest.mark.parametrize("kind", ["usage", "adjustment"])
def test_741_referenced_supply_cannot_delete_or_reassign(env, kind):
    client, Session = env
    sid, _, cid = seed(Session)
    with Session() as db:
        s = db.get(Supply, sid)
        if kind == "usage":
            s.remaining_qty -= 1
            db.add(SupplyUsage(supply_id=sid, amount=1))
        else:
            db.add(InventoryAdjustment(
                supply_id=sid, previous_qty=10, counted_qty=10,
                reason="Count verified",
            ))
        db.commit()
    v, html = version(client, sid)
    assert 'data-macd741-supply-guard' in html
    assert f'action="/supplies/{sid}/delete"' not in html
    request = dict(version=v, name="New", notes="new",
                   kind="syringe", compound_id=str(cid))
    allowed_metadata = post(client, f"/supplies/{sid}/edit", {
        **request, "kind": "needle",
    })
    assert "err=" not in allowed_metadata.headers["location"]
    v2, _ = version(client, sid)
    blocked = post(client, f"/supplies/{sid}/edit", {
        **request, "version": v2,
    })
    assert "err=" in blocked.headers["location"]
    denied = post(client, f"/supplies/{sid}/delete", {
        "version": v2, "confirm_delete": "delete",
    })
    assert "err=" in denied.headers["location"]
    with Session() as db:
        assert db.get(Supply, sid).name == "New"
        assert db.get(Supply, sid).kind == "needle"
        if kind == "usage":
            assert db.scalar(select(SupplyUsage.amount)) == 1
        else:
            assert db.scalar(select(InventoryAdjustment.reason)) == "Count verified"


def test_741_stale_stock_form_and_confirmation_fail_closed(env):
    client, Session = env
    sid, _, cid = seed(Session)
    old, _ = version(client, sid)
    with Session() as db:
        db.get(Supply, sid).remaining_qty = 8
        db.commit()
    denied = post(client, f"/supplies/{sid}/edit", dict(
        version=old, name="Changed", notes="", kind="needle",
        compound_id=str(cid),
    ))
    assert "err=" in denied.headers["location"]
    no_confirmation = post(client, f"/supplies/{sid}/delete", dict(
        version=old, confirm_delete="",
    ))
    assert "err=" in no_confirmation.headers["location"]
    stale = post(client, f"/supplies/{sid}/delete", dict(
        version=old, confirm_delete="delete",
    ))
    assert "err=" in stale.headers["location"]
    with Session() as db:
        assert db.get(Supply, sid).name == "Test Needle"


def test_741_delete_unused_supply_preserves_purchase_and_audits(env):
    client, Session = env
    sid, pid, _ = seed(Session)
    v, _ = version(client, sid)
    response = post(client, f"/supplies/{sid}/delete", dict(
        version=v, confirm_delete="delete",
    ))
    assert response.status_code == 303 and "err=" not in response.headers["location"]
    with Session() as db:
        assert db.get(Supply, sid) is None
        assert db.get(Purchase, pid) is not None
        audit = db.scalar(select(ChangeAudit).where(
            ChangeAudit.entity_type == "supply",
            ChangeAudit.action == "delete", ChangeAudit.entity_id == sid,
        ))
        assert json.loads(audit.before_json)["purchase_id"] == pid
    assert post(client, f"/supplies/{sid}/delete", dict(
        version=v, confirm_delete="delete",
    )).status_code == 404


def test_741_custom_category_edit_and_guarded_deletion(env):
    client, Session = env
    with Session() as db:
        cat = SupplyCategory(key="glassware", label="Glassware", unit="count")
        db.add(cat)
        db.commit()
        cid = cat.id
    v = category_version(client, cid)
    renamed = post(client, f"/supplies/categories/{cid}/edit", dict(
        version=v, label="Glass ware", unit="packs",
    ))
    assert "err=" not in renamed.headers["location"]
    with Session() as db:
        assert (db.get(SupplyCategory, cid).label, db.get(SupplyCategory, cid).unit) == (
            "Glass ware", "packs",
        )
    stale = post(client, f"/supplies/categories/{cid}/delete", dict(
        version=v, confirm_delete="delete",
    ))
    assert "err=" in stale.headers["location"]
    fresh = category_version(client, cid)
    deleted = post(client, f"/supplies/categories/{cid}/delete", dict(
        version=fresh, confirm_delete="delete",
    ))
    assert "err=" not in deleted.headers["location"]
    with Session() as db:
        assert db.get(SupplyCategory, cid) is None
        audits = list(db.scalars(select(ChangeAudit).where(
            ChangeAudit.entity_type == "supply_category",
            ChangeAudit.entity_id == cid,
        )))
        assert {x.action for x in audits} == {"edit", "delete"}


def test_741_builtin_category_and_custom_category_with_stock_protected(env):
    client, Session = env
    sid, _, _ = seed(Session)
    with Session() as db:
        built_in = db.scalar(select(SupplyCategory).where(
            SupplyCategory.key == "needle",
        ))
        builtin_id = built_in.id
        cid = SupplyCategory(key="other_custom", label="Custom", unit="count")
        db.add(cid)
        db.commit()
        cid = cid.id
        db.get(Supply, sid).kind = "other_custom"
        db.commit()
    denied = post(client, f"/supplies/categories/{builtin_id}/delete", dict(
        version="forged", confirm_delete="delete",
    ))
    assert "err=" in denied.headers["location"]
    v = category_version(client, cid)
    unit_change = post(client, f"/supplies/categories/{cid}/edit", dict(
        version=v, label="Custom", unit="mL",
    ))
    assert "err=" in unit_change.headers["location"]
    reject_delete = post(client, f"/supplies/categories/{cid}/delete", dict(
        version=v, confirm_delete="delete",
    ))
    assert "err=" in reject_delete.headers["location"]
    with Session() as db:
        assert db.get(SupplyCategory, cid).unit == "count"



def test_741_custom_category_used_by_reusable_purchase_template_is_protected(env):
    client, Session = env
    with Session() as db:
        c = SupplyCategory(key="template_pack", label="Template Packs", unit="packs")
        db.add(c)
        db.flush()
        cid = c.id
        db.add(SupplyProduct(
            name="Future reusable pack", kind="template_pack",
            package_type="box", units_per_pack=12,
        ))
        db.commit()
    v = category_version(client, cid)
    change = post(client, f"/supplies/categories/{cid}/edit", dict(
        version=v, label="New Name", unit="count",
    ))
    assert "err=" in change.headers["location"]
    deletion = post(client, f"/supplies/categories/{cid}/delete", dict(
        version=v, confirm_delete="delete",
    ))
    assert "err=" in deletion.headers["location"]
    with Session() as db:
        assert db.get(SupplyCategory, cid).unit == "packs"


def test_741_confirmation_scripts_do_not_embed_untrusted_record_names():
    for path in ("supplies.html", "pages.html", "protocols.html"):
        html = (ROOT / "app/templates" / path).read_text()
        for line in html.splitlines():
            if "return confirm(" in line:
                assert "{{" not in line and "}}" not in line, (path, line)


def test_741_notes_delete_audit_preserves_no_body_text(env):
    client, Session = env
    with Session() as db:
        p = Page(title="Test Note", body="Private content to delete",
                 tags="test")
        db.add(p)
        db.commit()
        pid = p.id
    html = client.get("/pages").text
    assert f'action="/pages/{pid}/delete"' in html
    assert f'href="/pages/{pid}/edit"' in html
    result = post(client, f"/pages/{pid}/delete", {})
    assert result.status_code == 303
    with Session() as db:
        assert db.get(Page, pid) is None
        audit = db.scalar(select(ChangeAudit).where(
            ChangeAudit.entity_type == "notes_page",
            ChangeAudit.entity_id == pid,
            ChangeAudit.action == "delete",
        ))
        assert audit and json.loads(audit.before_json)["title"] == "Test Note"
        assert "Private content to delete" not in audit.before_json


@pytest.mark.parametrize("template", [
    "supplies.html", "coas.html", "coa_edit.html", "vials.html",
    "vial_detail.html", "blend_detail.html", "labs.html", "lab_report.html",
    "protocols.html", "calendar.html", "pages.html", "page_view.html",
])
def test_741_integrated_templates_parse_have_scoped_asset_and_real_actions(template):
    src = (ROOT / "app/templates" / template).read_text()
    Environment().parse(src)
    assert "/static/css/tracker-integrated-macd741.css?v=741" in src
    assert 'tracker-macd741-action' in src


@pytest.mark.parametrize("width", [320, 390, 430, 760, 1024])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_741_macd_controls_fit_phone_and_show_native_disclosure(width, scheme):
    from playwright.sync_api import expect, sync_playwright
    html = (
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<div class="tracker-macd741-page"><div class="tracker-macd741-actions">'
        '<details class="tracker-macd741-disclosure"><summary class="tracker-macd741-action">'
        'Edit supply</summary><form class="tracker-macd741-edit"><label>Supply name'
        '<input value="Sterile syringes"></label><label>Category<select>'
        '<option>Needles</option></select></label><label>Notes<textarea></textarea>'
        '</label><button class="tracker-macd741-action">Save supply changes</button>'
        '</form></details><form><button class="tracker-macd741-action">Delete supply</button>'
        '</form></div></div>'
    )
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                viewport={"width": width, "height": 844},
                color_scheme=scheme,
            )
            page.set_content(html)
            page.add_style_tag(content=CSS.read_text())
            summary = page.locator(".tracker-macd741-disclosure > summary")
            delete = page.get_by_role("button", name="Delete supply")
            expect(summary).to_be_visible()
            expect(delete).to_be_visible()
            assert summary.evaluate("el => getComputedStyle(el).display == 'list-item'")
            assert summary.evaluate("el => el.getBoundingClientRect().height >= 44")
            assert delete.evaluate("el => el.getBoundingClientRect().height >= 44")
            summary.click()
            expect(page.get_by_role("button", name="Save supply changes")).to_be_visible()
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth + 1"
            ), (width, scheme)
        finally:
            browser.close()


def test_741_calendar_projections_link_back_to_source_protocol():
    source = (ROOT / "app/routers/calendar.py").read_text()
    html = (ROOT / "app/templates/calendar.html").read_text()
    assert "'protocol_id': protocol.id" in source
    assert 'href="/protocols/{{ x.protocol_id }}"' in html
    assert 'action="/calendar/exclude"' in html
    assert 'action="/calendar/exclusions/{{ rule.id }}/restore"' in html


def test_741_blend_source_custody_and_edit_withdrawal_remain_unchanged():
    src = (ROOT / "app/templates/blend_detail.html").read_text()
    assert 'href="/vials/{{ c.source_vial_id }}"' in src
    assert 'href="/doses/blends/{{ dose.id }}/edit"' in src
    assert "Whole-blend deletion is not offered" in src


def test_741_existing_mgmt_paths_are_native_not_fake_buttons():
    expectations = {
        "protocols.html": [
            'action="/protocols/{{ r.p.id }}/active"',
            'action="/protocols/{{ r.p.id }}/duplicate"',
            'action="/protocols/{{ r.p.id }}/delete"',
        ],
        "lab_report.html": [
            'action="/labs/{{ rep.id }}/edit"',
            'action="/labs/{{ rep.id }}/delete"',
        ],
        "coa_edit.html": [
            'action="/coas/{{ coa.id }}/attachments"',
            'action="/coas/{{ coa.id }}/assign"',
            'action="/coas/{{ coa.id }}/delete"',
        ],
        "vial_detail.html": [
            'action="/vials/{{ v.id }}/delete"',
            'action="/vials/{{ v.id }}"',
        ],
    }
    for path, strings in expectations.items():
        contents = (ROOT / "app/templates" / path).read_text()
        for value in strings:
            assert value in contents, (path, value)
