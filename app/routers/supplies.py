import math
import json
from hashlib import sha256
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..scoped_db390 import get_scoped_db390
from ..models import Purchase, Supply, SupplyUsage, Compound, SupplyCategory, InventoryAdjustment, ChangeAudit
from ..supply_categories import DEFAULTS, ensure_categories, validate_supply
from .. import services, idempotency
from ..inventory_lock import reserve_inventory_write
from ..templating import render
router = APIRouter()


def _supply_snapshot741(s: Supply) -> dict:
    # Includes stock state to reject stale edits after a simultaneous dose/use.
    return {"id": s.id, "purchase_id": s.purchase_id, "name": s.name,
            "kind": s.kind, "compound_id": s.compound_id, "notes": s.notes or "",
            "purchased_qty": s.purchased_qty, "remaining_qty": s.remaining_qty,
            "unit_price_cents": s.unit_price_cents,
            "bulk_pack_count": s.bulk_pack_count,
            "bulk_units_per_pack": s.bulk_units_per_pack,
            "bulk_total_cents": s.bulk_total_cents}


def _supply_version741(s: Supply) -> str:
    return sha256(json.dumps(_supply_snapshot741(s),
                             sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _category_version741(c: SupplyCategory) -> str:
    return sha256(json.dumps([c.id, c.key, c.label, c.unit],
                             separators=(",", ":")).encode()).hexdigest()


def _custom_category741(c: SupplyCategory) -> bool:
    return c.key not in {key for key, _, _ in DEFAULTS}


def _category_supply_counts741(db: Session) -> dict[str, int]:
    return dict(db.execute(select(Supply.kind, func.count()).group_by(Supply.kind)))


def _supply_references741(db: Session) -> dict[int, dict[str, int]]:
    refs: dict[int, dict[str, int]] = {}
    for key, model in (("usage", SupplyUsage), ("adjustments", InventoryAdjustment)):
        for sid, n in db.execute(select(model.supply_id, func.count()).group_by(model.supply_id)):
            refs.setdefault(sid, {"usage": 0, "adjustments": 0})[key] = n
    return refs


@router.get("/supplies")
def index(request: Request, db: Session = Depends(get_scoped_db390)):
    categories = ensure_categories(db)
    supplies = list(db.scalars(select(Supply).order_by(Supply.id.desc())))
    return render(request, "supplies.html", categories=categories, category_map={c.key: c for c in categories}, supplies=supplies, submission_tokens={s.id: idempotency.new_token() for s in supplies}, purchases=list(db.scalars(select(Purchase).order_by(Purchase.id.desc()))), compounds=list(db.scalars(select(Compound).order_by(Compound.name))), supply_versions741={s.id: _supply_version741(s) for s in supplies}, supply_references741=_supply_references741(db), category_versions741={c.id: _category_version741(c) for c in categories}, category_supply_counts741=_category_supply_counts741(db), custom_category741=_custom_category741)

@router.post("/supplies")
def add(purchase_id: int = Form(...), name: str = Form(...), kind: str = Form(...), quantity: float = Form(...), unit_price: str = Form("0"), pack_count: str = Form(""),
        units_per_pack: str = Form(""), package_price: str = Form(""), compound_id: str = Form(""), db: Session = Depends(get_scoped_db390)):
    if not reserve_inventory_write(db):
        return services.flash_redirect("/supplies", err="Inventory is busy. Please retry.")
    ensure_categories(db)
    try:
        from .purchases import parse_bulk
        quantity, bulk_count, bulk_size, bulk_cents = parse_bulk(
            db, kind, quantity, pack_count, units_per_pack, package_price)
        if not name.strip(): raise ValueError("Name is required.")
    except ValueError as exc:
        return services.flash_redirect("/supplies", err=str(exc))
    if not db.get(Purchase, purchase_id):
        raise HTTPException(404)
    cid = int(compound_id) if compound_id else None
    if cid and not db.get(Compound, cid):
        raise HTTPException(404)
    db.add(Supply(purchase_id=purchase_id, name=name.strip(), kind=kind, compound_id=cid, purchased_qty=quantity, remaining_qty=quantity, unit_price_cents=services.to_cents(unit_price),
                  bulk_pack_count=bulk_count, bulk_units_per_pack=bulk_size, bulk_total_cents=bulk_cents))
    db.commit()
    return services.flash_redirect("/supplies", msg="Supply added.")

@router.post("/supplies/{sid}/edit")
def edit_supply741(
    sid: int, version: str = Form(""), name: str = Form(""), notes: str = Form(""),
    kind: str = Form(""), compound_id: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    """Edit stock metadata without rewriting purchase or usage quantities."""
    back = f"/supplies#tracker-supply-{sid}"
    if not reserve_inventory_write(db):
        return services.flash_redirect(back, err="Inventory is busy. Please retry.")
    s = db.get(Supply, sid)
    if s is None:
        db.rollback()
        raise HTTPException(404, "Supply not found")
    before = _supply_snapshot741(s)
    if version != _supply_version741(s):
        db.rollback()
        return services.flash_redirect(back, err="Supply changed. Reload before editing.")
    name, notes = name.strip(), notes.strip()
    if not name or len(name) > 160 or len(notes) > 2000:
        db.rollback()
        return services.flash_redirect(back, err="Enter a name (up to 160) and notes (up to 2000).")
    old_category = db.scalar(select(SupplyCategory).where(SupplyCategory.key == s.kind))
    new_category = db.scalar(select(SupplyCategory).where(SupplyCategory.key == kind))
    if new_category is None or old_category is None:
        db.rollback()
        return services.flash_redirect(back, err="Choose a valid supply category.")
    try:
        cid = int(compound_id) if compound_id.strip() else None
    except ValueError:
        db.rollback()
        return services.flash_redirect(back, err="Invalid compound.")
    if cid is not None and db.get(Compound, cid) is None:
        db.rollback()
        return services.flash_redirect(back, err="Compound not found.")
    refs = _supply_references741(db).get(sid, {})
    historic = bool(refs.get("usage") or refs.get("adjustments"))
    if (kind != s.kind and (historic or old_category.unit != new_category.unit
                              or s.kind in ("bac_water", "pill")
                              or kind in ("bac_water", "pill"))):
        db.rollback()
        return services.flash_redirect(
            back, err="Category reassignment requires unused stock and matching units; BAC water and pills retain their original type."
        )
    if cid != s.compound_id and historic:
        db.rollback()
        return services.flash_redirect(back, err="Cannot reassign a compound after stock use or reconciliation.")
    s.name, s.notes, s.kind, s.compound_id = name, notes, kind, cid
    after = _supply_snapshot741(s)
    if before == after:
        db.rollback()
        return services.flash_redirect(back, msg="Supply unchanged.")
    db.add(ChangeAudit(
        entity_type="supply", entity_id=sid, action="edit",
        before_json=json.dumps(before), after_json=json.dumps(after),
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return services.flash_redirect(back, err="Supply edit conflicts with linked inventory.")
    return services.flash_redirect(back, msg="Supply details saved. Stock history retained.")


@router.post("/supplies/{sid}/delete")
def delete_supply741(
    sid: int, version: str = Form(""), confirm_delete: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    """Only delete an unused, never-reconciled purchase supply line."""
    back = f"/supplies#tracker-supply-{sid}"
    if not reserve_inventory_write(db):
        return services.flash_redirect(back, err="Inventory is busy. Please retry.")
    s = db.get(Supply, sid)
    if s is None:
        db.rollback()
        raise HTTPException(404, "Supply not found")
    if confirm_delete != "delete":
        db.rollback()
        return services.flash_redirect(back, err="Confirm deletion of this unused supply.")
    if version != _supply_version741(s):
        db.rollback()
        return services.flash_redirect(back, err="Supply changed. Reload before deleting.")
    if any(_supply_references741(db).get(sid, {}).values()):
        db.rollback()
        return services.flash_redirect(
            back, err="Supply has recorded use or stock adjustments; deletion is unavailable."
        )
    db.add(ChangeAudit(
        entity_type="supply", entity_id=sid, action="delete",
        before_json=json.dumps(_supply_snapshot741(s)), after_json="{}",
    ))
    db.delete(s)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return services.flash_redirect(back, err="Supply has dependent records; deletion blocked.")
    return services.flash_redirect("/supplies", msg="Unused supply deleted; audit preserved.")


@router.post("/supplies/{sid}/use")
def use(sid: int, quantity: float = Form(...), submission_token: str = Form(""), db: Session = Depends(get_scoped_db390)):
    if not reserve_inventory_write(db):
        return services.flash_redirect("/supplies", err="Inventory is busy. Please retry.")
    state, digest = idempotency.check(db, submission_token, "supply_use", {"sid": sid, "quantity": quantity})
    if submission_token and state != "new":
        db.rollback()
        return services.flash_redirect("/supplies", msg="This usage was already recorded." if state == "replay" else "", err="Invalid or reused submission identifier. Refresh the page." if state != "replay" else "")
    s = db.get(Supply, sid)
    if not s: raise HTTPException(404)
    category = db.query(SupplyCategory).filter_by(key=s.kind).first()
    if not math.isfinite(quantity) or quantity <= 0 or quantity > s.remaining_qty + 1e-9 or (category and category.unit == "count" and not float(quantity).is_integer()):
        db.rollback()
        return services.flash_redirect("/supplies", err="Invalid quantity or insufficient stock.")
    s.remaining_qty -= quantity
    db.add(SupplyUsage(supply_id=sid, amount=quantity))
    if submission_token:
        idempotency.record(db, submission_token, "supply_use", digest)
    db.commit()
    return services.flash_redirect("/supplies", msg="Usage recorded.")

@router.post('/supplies/{sid}/dose')
def log_pill(sid: int, quantity: int = Form(...), taken_at: str = Form(''), notes: str = Form(''),
             submission_token: str = Form(''), db: Session = Depends(get_scoped_db390)):
    # Reserve the SQLite write transaction BEFORE reading remaining stock.
    if not reserve_inventory_write(db):
        return services.flash_redirect('/supplies', err='Inventory is busy. Please retry.')
    state, digest = idempotency.check(db, submission_token, 'pill_use',
                                      {'sid': sid, 'quantity': quantity, 'taken_at': taken_at, 'notes': notes})
    if submission_token and state != 'new':
        db.rollback()
        return services.flash_redirect('/supplies',
            msg='This pill usage was already recorded.' if state == 'replay' else '',
            err='Invalid or reused submission identifier. Refresh the page.' if state != 'replay' else '')
    s = db.get(Supply, sid)
    if not s:
        db.rollback()
        raise HTTPException(404)
    if s.kind != 'pill' or quantity <= 0 or quantity > s.remaining_qty:
        db.rollback()
        return services.flash_redirect('/supplies', err='Invalid pill quantity or insufficient stock.')
    s.remaining_qty -= quantity
    db.add(SupplyUsage(supply_id=s.id, amount=quantity))
    if submission_token:
        idempotency.record(db, submission_token, 'pill_use', digest)
    db.commit()
    return services.flash_redirect('/supplies', msg=f'Recorded {quantity} pill(s) used.')

@router.post("/supplies/categories/{cid}/edit")
def edit_category741(
    cid: int, version: str = Form(""), label: str = Form(""), unit: str = Form("count"),
    db: Session = Depends(get_scoped_db390),
):
    if not reserve_inventory_write(db):
        return services.flash_redirect("/supplies#tracker-categories", err="Inventory is busy.")
    cat = db.get(SupplyCategory, cid)
    if cat is None:
        db.rollback()
        raise HTTPException(404, "Category not found")
    label = label.strip()
    if not _custom_category741(cat):
        db.rollback()
        return services.flash_redirect("/supplies#tracker-categories", err="Built-in category definitions cannot be edited.")
    if version != _category_version741(cat):
        db.rollback()
        return services.flash_redirect("/supplies#tracker-categories", err="Category changed; reload before editing.")
    if not label or len(label) > 100 or unit not in ("count", "mL", "g", "mg", "L", "boxes", "packs"):
        db.rollback()
        return services.flash_redirect("/supplies#tracker-categories", err="Enter a valid category name and unit.")
    if unit != cat.unit and db.scalar(select(func.count()).select_from(Supply).where(Supply.kind == cat.key)):
        db.rollback()
        return services.flash_redirect("/supplies#tracker-categories", err="Cannot change the unit of a category with stock; create another category instead.")
    before = {"key": cat.key, "label": cat.label, "unit": cat.unit}
    after = {"key": cat.key, "label": label, "unit": unit}
    if before == after:
        db.rollback()
        return services.flash_redirect("/supplies#tracker-categories", msg="Category unchanged.")
    duplicate = db.scalar(select(SupplyCategory.id).where(
        SupplyCategory.label == label, SupplyCategory.id != cid
    ))
    if duplicate is not None:
        db.rollback()
        return services.flash_redirect("/supplies#tracker-categories", err="Category name already exists.")
    cat.label, cat.unit = label, unit
    db.add(ChangeAudit(entity_type="supply_category", entity_id=cid, action="edit",
                       before_json=json.dumps(before), after_json=json.dumps(after)))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return services.flash_redirect("/supplies#tracker-categories", err="Category could not be saved.")
    return services.flash_redirect("/supplies#tracker-categories", msg="Category saved.")


@router.post("/supplies/categories/{cid}/delete")
def delete_category741(
    cid: int, version: str = Form(""), confirm_delete: str = Form(""),
    db: Session = Depends(get_scoped_db390),
):
    if not reserve_inventory_write(db):
        return services.flash_redirect("/supplies#tracker-categories", err="Inventory is busy.")
    cat = db.get(SupplyCategory, cid)
    if cat is None:
        db.rollback()
        raise HTTPException(404, "Category not found")
    if not _custom_category741(cat) or version != _category_version741(cat) or confirm_delete != "delete":
        db.rollback()
        return services.flash_redirect("/supplies#tracker-categories", err="Category is built-in, changed, or deletion was not confirmed.")
    if db.scalar(select(func.count()).select_from(Supply).where(Supply.kind == cat.key)):
        db.rollback()
        return services.flash_redirect("/supplies#tracker-categories", err="Category contains supplies and cannot be deleted.")
    db.add(ChangeAudit(entity_type="supply_category", entity_id=cid, action="delete",
                       before_json=json.dumps({"key": cat.key, "label": cat.label, "unit": cat.unit}),
                       after_json="{}"))
    db.delete(cat)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return services.flash_redirect("/supplies#tracker-categories", err="Category has dependent records.")
    return services.flash_redirect("/supplies#tracker-categories", msg="Unused custom category deleted.")


@router.post("/supplies/categories")
def create_category(label: str = Form(...), unit: str = Form("count"), db: Session = Depends(get_scoped_db390)):
    if not reserve_inventory_write(db):
        return services.flash_redirect("/supplies", err="Inventory is busy. Please retry.")
    import re
    ensure_categories(db)
    label = label.strip()[:100]
    if not label or unit not in ("count", "mL", "g", "mg", "L", "boxes", "packs"):
        return services.flash_redirect("/supplies", err="Enter a category name and valid unit.")
    key = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:20]
    if not key or db.query(SupplyCategory).filter((SupplyCategory.key == key) | (SupplyCategory.label == label)).first():
        return services.flash_redirect("/supplies", err="Category already exists or has an invalid name.")
    db.add(SupplyCategory(key=key, label=label, unit=unit))
    db.commit()
    return services.flash_redirect("/supplies", msg="Category created. It is now available on purchases and supplies.")
