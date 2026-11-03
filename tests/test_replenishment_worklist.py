"""Replenishment worklist tests use the pytest-isolated Tracker database.

All endpoints are read-only. Real inventory, purchasing and administration
records must remain untouched.
"""
import csv
import io
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select, func

from app.main import app
from app.db import SessionLocal
from app.models import Compound, DoseLog, Protocol, ProtocolItem, Purchase, Supply, SupplyUsage, Vial
from app.replenishment_review import (
    build_replenishment, classify_forecast, safe_csv_text,
)


def sample(*, name="Example", remaining=4, used=20, days_left=6,
           unit="mcg"):
    return {
        "name": name, "remaining": remaining, "used": used,
        "days_left": days_left, "unit": unit,
        "depletion": date(2026, 11, 8),
    }


def test_depleted_stock_is_distinct_from_estimated_shortfall():
    cid = {"Example": 9}
    no_stock = classify_forecast("Compound", sample(remaining=0, days_left=None),
                                 21, cid)
    assert no_stock["state"] == "depleted"
    assert no_stock["review_href"] == "/vials?status=active&compound_id=9"
    assert no_stock["purchase_href"] == "/purchases#new-purchase"
    near = classify_forecast("Compound", sample(days_left=12), 21, cid)
    assert near["state"] == "soon"
    assert "Estimated" in near["label"]


def test_no_history_is_unestimated_not_out_of_stock():
    row = classify_forecast("Supply", sample(remaining=18, used=0,
                                            days_left=None), 21, {})
    assert row["state"] == "unestimated"
    assert row["review_href"] == "/supplies#supply-stock"
    assert row["remaining"] == 18
    assert row["unit"] == ""
    assert row["days_left"] is None


def test_supply_unit_comes_from_inventory_category_not_mass_assumption():
    row = classify_forecast(
        "Supply", sample(name="BAC", remaining=3, used=2, days_left=10),
        21, {}, supply_unit="mL",
    )
    assert row["unit"] == "mL"


def test_healthy_coverage_is_not_an_alert():
    assert classify_forecast("Compound", sample(days_left=24),
                             21, {}) is None
    assert classify_forecast("Compound", sample(days_left=21),
                             21, {})["state"] == "soon"


def test_invalid_forecasts_never_claim_stock_coverage():
    for value in (-1, float("nan"), float("inf"), None):
        assert classify_forecast(
            "Supply", sample(remaining=value), 21, {},
        ) is None
    assert classify_forecast(
        "Supply", sample(remaining=2, days_left=float("nan")), 21, {},
    )["state"] == "unestimated"


def test_csv_cell_safety_for_controlled_product_names():
    for prefix in ("=", "+", "-", "@", "\t", "\n"):
        assert safe_csv_text(prefix + "cmd").startswith("'")
    assert safe_csv_text("Ordinary item") == "Ordinary item"


def test_builder_refuses_unadvertised_horizons_before_query():
    with TestClient(app):
        with SessionLocal() as db:
            for days, horizon in ((31, 21), (30, 22), (0, 21)):
                try:
                    build_replenishment(db, history_days=days,
                                        horizon_days=horizon)
                except ValueError:
                    pass
                else:
                    raise AssertionError("Invalid forecast selector accepted")


def seed_items():
    suffix = uuid4().hex
    name = "WorklistCompound-" + suffix
    unknown_name = "Unestimated-" + suffix
    supply_name = "WorklistSupply-" + suffix
    with SessionLocal() as db:
        compound = Compound(name=name, category="peptide")
        unknown = Compound(name=unknown_name, category="peptide")
        order = Purchase(vendor="Worklist test " + suffix,
                         purchased_on=date.today())
        db.add_all([compound, unknown, order])
        db.flush()
        vial = Vial(
            compound_id=compound.id, content_value=10,
            content_unit="mg", volume_ml=1, status="in_use",
        )
        unknown_vial = Vial(
            compound_id=unknown.id, content_value=6,
            content_unit="mg", volume_ml=1, status="sealed",
        )
        supply = Supply(
            purchase_id=order.id, name=supply_name, kind="needle",
            purchased_qty=12, remaining_qty=2, unit_price_cents=10,
        )
        db.add_all([vial, unknown_vial, supply])
        db.flush()
        db.add(DoseLog(
            vial_id=vial.id,
            taken_at=datetime.now() - timedelta(days=1),
            entered_value=9, entered_unit="mg", amount_base=9000,
            kind="dose",
        ))
        db.add(SupplyUsage(
            supply_id=supply.id, amount=10,
            created_at=datetime.now() - timedelta(days=1),
        ))
        db.commit()
        return name, unknown_name, supply_name, compound.id


def test_http_board_links_and_reuses_actual_inventory_forecast():
    with TestClient(app) as client:
        name, unknown, supply_name, cid = seed_items()
        page = client.get("/replenishment-review?days=30&horizon=14")
        assert page.status_code == 200
        assert name in page.text
        assert supply_name in page.text
        assert unknown in page.text
        assert 'data-replenishment-state="soon"' in page.text
        assert 'data-replenishment-state="unestimated"' in page.text
        assert f'/vials?status=active&amp;compound_id={cid}' in page.text
        assert "/purchases#new-purchase" in page.text
    assert f"{supply_name}</td>" in page.text
        assert '/supplies#supply-stock' in page.text
        assert '/replenishment-review.csv?days=30&amp;horizon=14' in page.text

        # Display only: opening the board does not create stock, orders or doses.
        with SessionLocal() as db:
            assert db.scalar(select(func.count()).select_from(Purchase)
                             .where(Purchase.vendor.like("Worklist test %"))) >= 1
            assert db.scalar(select(func.count()).select_from(DoseLog)
                             .join(Vial).join(Compound)
                             .where(Compound.name == name)) == 1


def test_csv_matches_web_selector_and_contains_no_reorder_quantities():
    with TestClient(app) as client:
        name, unknown, supply_name, _ = seed_items()
        response = client.get("/replenishment-review.csv?days=30&horizon=14")
    assert response.status_code == 200
    assert response.headers["content-disposition"].endswith('"replenishment-review.csv"')
    assert "no-store" in response.headers["cache-control"]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    selected = {row["Item"]: row for row in rows}
    assert name in selected
    assert unknown in selected
    assert supply_name in selected
    assert selected[name]["Status"] == "Estimated depletion within horizon"
    assert selected[unknown]["Status"] == "Insufficient recorded usage to estimate"
    assert selected[name]["History window days"] == "30"
    assert selected[name]["Review horizon days"] == "14"
    assert "Reorder quantity" not in rows[0]


def test_bad_query_choices_return_422_not_500():
    with TestClient(app) as client:
        for endpoint in ("/replenishment-review",
                         "/replenishment-review.csv"):
            assert client.get(endpoint + "?days=44&horizon=21").status_code == 422
            assert client.get(endpoint + "?days=30&horizon=22").status_code == 422


def test_integration_reuses_existing_inventory_routes():
    with TestClient(app, follow_redirects=False) as client:
        for endpoint in (
            "/inventory-alerts", "/inventory-intelligence",
            "/purchases", "/vials", "/supplies",
        ):
            response = client.get(endpoint)
            assert response.status_code == 200


def test_navigation_and_purchase_anchor_are_present():
    root = Path(__file__).resolve().parents[1]
    base = (root / "app/templates/base.html").read_text()
    alerts = (root / "app/templates/inventory_alerts.html").read_text()
    supplies = (root / "app/templates/supplies.html").read_text()
    purchases = (root / "app/templates/purchases.html").read_text()
    assert "('/replenishment-review','Replenishment review')" in base
    assert 'href="/replenishment-review"' in alerts
    assert 'id="supply-stock"' in supplies
    assert 'id="new-purchase"' in purchases


def test_active_protocol_compound_with_no_vials_is_surfaced():
    suffix = uuid4().hex
    with TestClient(app) as client:
        with SessionLocal() as db:
            active_compound = Compound(name="NoStockActive-" + suffix)
            inactive_compound = Compound(name="NoStockWhatIf-" + suffix)
            ended_compound = Compound(name="NoStockEnded-" + suffix)
            db.add_all([active_compound, inactive_compound, ended_compound])
            db.flush()
            active = Protocol(
                name="Active unstocked", is_active=True,
                start_date=date.today(),
            )
            draft = Protocol(name="What-if unstocked", is_active=False,
                             start_date=date.today())
            ended = Protocol(name="Ended unstocked", is_active=True,
                             start_date=date.today() - timedelta(days=90),
                             end_date=date.today() - timedelta(days=1))
            for p, compound in (
                (active, active_compound),
                (draft, inactive_compound),
                (ended, ended_compound),
            ):
                p.items.append(ProtocolItem(
                    compound_id=compound.id, amount_value=1,
                    amount_unit="mg", freq_count=1, freq_period="week",
                    start_week=1, position=0,
                ))
            db.add_all([active, draft, ended])
            db.commit()
            cid = active_compound.id

        page = client.get("/replenishment-review?days=30&horizon=21")
    assert page.status_code == 200
    assert "NoStockActive-" + suffix in page.text
    assert "No usable active vial stock for active protocol" in page.text
    assert f"/vials?status=all&amp;compound_id={cid}" in page.text
    assert "NoStockWhatIf-" + suffix not in page.text
    assert "NoStockEnded-" + suffix not in page.text


def test_active_future_protocol_outside_horizon_not_shown_as_now_unstocked():
    suffix = uuid4().hex
    with TestClient(app) as client:
        with SessionLocal() as db:
            compound = Compound(name="FutureNoStock-" + suffix)
            protocol = Protocol(name="Future unstocked", is_active=True,
                                start_date=date.today() + timedelta(days=200))
            protocol.items.append(ProtocolItem(
                compound=compound, amount_value=1, amount_unit="mg",
                freq_count=1, freq_period="week", start_week=1,
                position=0,
            ))
            db.add(protocol)
            db.commit()
        page = client.get("/replenishment-review?days=30&horizon=21")
    assert page.status_code == 200
    assert "FutureNoStock-" + suffix not in page.text
