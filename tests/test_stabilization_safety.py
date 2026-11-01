"""Regression coverage for vial deletion and kit-level price allocation.

All writes use a temporary, isolated SQLite database with foreign keys enabled.
No production data, migrations, or authentication are involved.
"""
from datetime import date, datetime
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models import (
    Blend, BlendComponent, ChangeAudit, Coa, Compound, DoseLog,
    PreparationEvent, Purchase, Supply, SupplyUsage, Vial,
)
from app.routers import purchases, vials


@pytest.fixture
def env(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'stabilization.sqlite3'}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def enforce_fks(conn, _record):
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session.begin() as db:
        compound = Compound(name="Stabilization Test", category="peptide")
        purchase = Purchase(vendor="Test Supplier", purchased_on=date(2026, 10, 31))
        db.add_all([compound, purchase])
        db.flush()
        ids = []
        for idx in range(4):
            vial = Vial(
                compound_id=compound.id,
                purchase_id=purchase.id,
                label=f"vial-{idx}",
                status="sealed",
                content_value=10,
                content_unit="mg",
                unit_price_cents=1000,
            )
            db.add(vial)
            db.flush()
            ids.append(vial.id)
        compound_id, purchase_id = compound.id, purchase.id

    app = FastAPI()
    app.include_router(vials.router)
    app.include_router(purchases.router)

    def get_test_db():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = get_test_db
    with TestClient(app, follow_redirects=False) as client:
        yield {
            "Session": Session, "client": client, "ids": ids,
            "compound_id": compound_id, "purchase_id": purchase_id,
        }
    engine.dispose()


def post_form(env, url, pairs):
    return env["client"].post(
        url, content=urlencode(pairs, doseq=True),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def preview(env, ids):
    response = post_form(
        env, "/vials/bulk/delete-preview",
        [("vial_ids", str(i)) for i in ids],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert len(data["snapshot"]) == 64
    return data


def delete(env, ids, snapshot=None):
    pairs = [("vial_ids", str(i)) for i in ids]
    if snapshot is not None:
        pairs.append(("delete_preview_snapshot", snapshot))
    return post_form(env, "/vials/bulk/delete", pairs)


def test_deletion_requires_a_fresh_preview(env):
    selected = env["ids"][:2]
    rejected = delete(env, selected)
    assert rejected.status_code == 303
    assert "err=" in rejected.headers["location"]
    with env["Session"]() as db:
        assert all(db.get(Vial, vid) is not None for vid in selected)


def test_successful_delete_keeps_certificate_and_audit(env):
    selected = [env["ids"][0]]
    with env["Session"].begin() as db:
        coa = Coa(original_name="test-coa.pdf", lab_name="Test lab")
        db.add(coa)
        db.flush()
        db.get(Vial, selected[0]).coa = coa
        coa_id = coa.id
    token = preview(env, selected)["snapshot"]
    response = delete(env, selected, token)
    assert response.status_code == 303
    assert "msg=" in response.headers["location"]
    with env["Session"]() as db:
        assert db.get(Vial, selected[0]) is None
        assert db.get(Coa, coa_id) is not None
        assert db.scalar(
            select(ChangeAudit).where(
                ChangeAudit.entity_type == "vial",
                ChangeAudit.entity_id == selected[0],
                ChangeAudit.action == "bulk_delete",
            )
        ) is not None


def test_changed_selection_is_not_deleted(env):
    selected = env["ids"][:2]
    token = preview(env, selected)["snapshot"]
    with env["Session"].begin() as db:
        db.get(Vial, selected[0]).label = "edited-after-preview"
    response = delete(env, selected, token)
    assert "err=" in response.headers["location"]
    with env["Session"]() as db:
        assert all(db.get(Vial, vid) is not None for vid in selected)


def test_dose_preparation_and_blend_block_deletion(env):
    first, second, third = env["ids"][:3]
    with env["Session"].begin() as db:
        db.add(DoseLog(
            vial_id=first, taken_at=datetime(2026, 10, 31),
            entered_value=1, entered_unit="mg", amount_base=1000,
        ))
        db.add(PreparationEvent(vial_id=second, kind="filtering"))
        blend = Blend(label="Test blend", final_volume_ml=2)
        db.add(blend)
        db.flush()
        db.add(BlendComponent(
            blend_id=blend.id, source_vial_id=third,
            compound_id=env["compound_id"],
            transferred_base=1000, transferred_ml=0.1,
            target_dose_base=100, target_unit="mcg",
        ))
    data = preview(env, [first, second, third])
    assert len(data["blocked"]) == 3
    response = delete(env, [first, second, third], data["snapshot"])
    assert "err=" in response.headers["location"]
    with env["Session"]() as db:
        assert all(db.get(Vial, vid) is not None for vid in (first, second, third))


def test_direct_supply_usage_is_blocked_but_other_vials_can_delete(env):
    protected, eligible = env["ids"][:2]
    with env["Session"].begin() as db:
        supply = Supply(
            purchase_id=env["purchase_id"], name="Needle", kind="needle",
            purchased_qty=10, remaining_qty=9, unit_price_cents=100,
        )
        db.add(supply)
        db.flush()
        db.add(SupplyUsage(supply_id=supply.id, vial_id=protected, amount=1))
    data = preview(env, [protected, eligible])
    assert [row["id"] for row in data["blocked"]] == [protected]
    assert "supply usage" in data["blocked"][0]["reason"]
    response = delete(env, [protected, eligible], data["snapshot"])
    assert "msg=" in response.headers["location"]
    with env["Session"]() as db:
        assert db.get(Vial, protected) is not None
        assert db.get(Vial, eligible) is None
        assert db.scalar(
            select(SupplyUsage).where(SupplyUsage.vial_id == protected)
        ) is not None


@pytest.mark.parametrize(
    "basis,kit_size,kit_count,price,expected_count,expected_total",
    [
        ("per_vial", 1, 1, "4.50", 2, 900),
        ("per_half_kit", 5, 2, "12.01", 10, 2402),
        ("per_full_kit", 10, 2, "19.99", 20, 3998),
    ],
)
def test_kit_price_preserves_exact_cents(
    env, basis, kit_size, kit_count, price, expected_count, expected_total,
):
    with env["Session"]() as db:
        before = {v.id for v in db.scalars(select(Vial))}
    response = post_form(
        env, f'/purchases/{env["purchase_id"]}/vials',
        [
            ("compound_id", str(env["compound_id"])),
            ("content_value", "10"), ("content_unit", "mg"),
            ("quantity", "2"), ("kit_size", str(kit_size)),
            ("kit_count", str(kit_count)),
            ("price_basis", basis), ("price_amount", price),
        ],
    )
    assert "msg=" in response.headers["location"]
    with env["Session"]() as db:
        new_vials = [
            vial for vial in db.scalars(select(Vial).order_by(Vial.id))
            if vial.id not in before
        ]
        assert len(new_vials) == expected_count
        assert sum(v.unit_price_cents for v in new_vials) == expected_total
        if kit_size > 1:
            for offset in range(0, len(new_vials), kit_size):
                assert sum(
                    vial.unit_price_cents
                    for vial in new_vials[offset:offset + kit_size]
                ) == expected_total // kit_count


def test_mismatched_price_basis_creates_no_vials(env):
    with env["Session"]() as db:
        before = db.query(Vial).count()
    response = post_form(
        env, f'/purchases/{env["purchase_id"]}/vials',
        [
            ("compound_id", str(env["compound_id"])),
            ("content_value", "10"), ("content_unit", "mg"),
            ("kit_size", "5"), ("kit_count", "2"),
            ("price_basis", "per_full_kit"), ("price_amount", "19.99"),
        ],
    )
    assert "err=" in response.headers["location"]
    with env["Session"]() as db:
        assert db.query(Vial).count() == before
