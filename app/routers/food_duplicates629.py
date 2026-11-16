"""Release 629: review and explicitly consolidate equivalent saved foods.

The read-only comparison shows all supported nutrients per serving.
A merge is allowed only when the complete nutrient payload, normalized name,
barcode and serving size match. It preserves recorded nutrient totals and
updates all known references transactionally.
"""
from collections import defaultdict
from hashlib import sha256
import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from ..food_storage_guard391 import require_food_storage391
from ..food_read_engine406 import get_food_read_engine406
from ..templating import render
from . import food, food_bundle376

router = APIRouter(dependencies=[Depends(require_food_storage391)])
MAX_PRODUCTS = 5000
MAX_MERGE = 30


def normalize629(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def nutrient_key629(raw):
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError("Saved food has invalid nutrient data") from None
    if type(parsed) is not dict:
        raise ValueError("Saved food nutrients must be an object")
    # Compare equivalent integer/float values numerically while retaining
    # unknown versus zero, original keys and nonstandard correction fields.
    # Booleans stay distinct from numbers.
    canonical = {
        key: (float(value) if type(value) in (int, float) else value)
        for key, value in parsed.items()
    }
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def compatible_key629(row):
    return (normalize629(row["name"]),
            normalize629(row["serving_description"]),
            normalize629(row["barcode"]),
            nutrient_key629(row["nutrients"]))


def init_review_schema630(db_engine):
    # Store acknowledgements separately, without changing historical food rows.
    with db_engine.begin() as db:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS tracker_food_duplicate_reviews630 (
                fingerprint TEXT PRIMARY KEY,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))


def group_fingerprint630(entries):
    # Any changes to names, servings, barcode, nutrition, or membership
    # invalidate a previous acknowledgement automatically.
    payload = [(row["id"], row["name"], row["serving_description"],
                row["barcode"], row["nutrients"])
               for row in sorted(entries, key=lambda row: row["id"])]
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                            separators=(",", ":")).encode("utf-8")).hexdigest()


def _fetch_products629(db):
    return db.execute(text("""
        SELECT p.id, p.name, p.barcode, p.serving_description,
               p.nutrients, p.source,
               COALESCE(e.total,0) AS log_count,
               COALESCE(t.total,0) AS template_count,
               CASE WHEN f.product_id IS NULL THEN 0 ELSE 1 END
                   AS favorite_count
        FROM tracker_food_products p
        LEFT JOIN (
            SELECT product_id, COUNT(*) AS total
            FROM tracker_food_entries GROUP BY product_id
        ) e ON e.product_id=p.id
        LEFT JOIN (
            SELECT product_id, COUNT(*) AS total
            FROM tracker_food_meal_template_items GROUP BY product_id
        ) t ON t.product_id=p.id
        LEFT JOIN tracker_food_favorites f ON f.product_id=p.id
        ORDER BY p.name COLLATE NOCASE, p.id
        LIMIT :limit
    """), {"limit": MAX_PRODUCTS + 1}).mappings().all()


def duplicate_groups629(db_engine, show_reviewed=False):
    food_bundle376.init_schema(db_engine)
    init_review_schema630(db_engine)
    with db_engine.connect() as db:
        rows = [dict(x) for x in _fetch_products629(db)]
        reviewed = set(db.execute(text(
            "SELECT fingerprint FROM tracker_food_duplicate_reviews630"
        )).scalars().all())
    limited = len(rows) > MAX_PRODUCTS
    rows = rows[:MAX_PRODUCTS]
    # Group candidates by shared normalized name OR nonempty barcode.
    # Connected groups are for review only; exact compatibility rules
    # still control whether any version may be consolidated.
    parents = {row["id"]: row["id"] for row in rows}

    def root(value):
        while parents[value] != value:
            parents[value] = parents[parents[value]]
            value = parents[value]
        return value

    seen = {}
    for row in rows:
        keys = [("name", normalize629(row["name"]))]
        barcode = normalize629(row["barcode"])
        if barcode:
            keys.append(("barcode", barcode))
        for key in keys:
            if not key[1]:
                continue
            if key in seen:
                parents[root(row["id"])] = root(seen[key])
            else:
                seen[key] = row["id"]

    groups = defaultdict(list)
    for row in rows:
        try:
            parsed = json.loads(row["nutrients"])
            if type(parsed) is not dict:
                raise ValueError("not an object")
            row["measurements"] = {
                name: parsed.get(name)
                for name in food.NUTRIENTS
            }
            row["match_key"] = compatible_key629(row)
            row["valid_nutrients"] = True
        except (TypeError, ValueError):
            row["measurements"] = {
                name: None for name in food.NUTRIENTS
            }
            row["match_key"] = None
            row["valid_nutrients"] = False
        groups[root(row["id"])].append(row)

    result = []
    for entries in groups.values():
        if len(entries) < 2:
            continue
        exact = defaultdict(list)
        for item in entries:
            if item["match_key"] is not None:
                exact[item["match_key"]].append(item)
        compatible = [group for group in exact.values() if len(group) > 1]
        differing = [
            nutrient for nutrient in food.NUTRIENTS
            if len({
                json.dumps(item["measurements"][nutrient],
                           sort_keys=True, default=str)
                for item in entries
            }) > 1
        ]
        fingerprint = group_fingerprint630(entries)
        if fingerprint in reviewed and not show_reviewed:
            continue
        result.append({
            "name": entries[0]["name"],
            "fingerprint": fingerprint,
            "reviewed": fingerprint in reviewed,
            "versions": entries,
            "equivalent_sets": compatible,
            "different_nutrients": differing,
            "different_values": len(exact) != 1 or any(
                not item["valid_nutrients"] for item in entries
            ),
        })
    result.sort(key=lambda group: normalize629(group["name"]))
    return {"groups": result, "examined": len(rows), "truncated": limited}


def mark_distinct630(db_engine, fingerprint):
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise ValueError("Invalid review selection")
    report = duplicate_groups629(db_engine, show_reviewed=True)
    group = next((g for g in report["groups"] if g["fingerprint"] == fingerprint), None)
    if group is None or not group["different_values"]:
        raise ValueError("Duplicate versions changed; refresh before reviewing")
    # Revalidate inside transaction and persist the exact fingerprint only.
    with db_engine.begin() as db:
        ids = [version["id"] for version in group["versions"]]
        rows = [db.execute(text("""
            SELECT id,name,serving_description,barcode,nutrients
            FROM tracker_food_products WHERE id=:id
        """), {"id": id_}).mappings().first() for id_ in ids]
        if any(row is None for row in rows) or group_fingerprint630(rows) != fingerprint:
            raise ValueError("Duplicate versions changed; refresh before reviewing")
        db.execute(text("""
            INSERT OR IGNORE INTO tracker_food_duplicate_reviews630(fingerprint)
            VALUES (:fingerprint)
        """), {"fingerprint": fingerprint})


def remove_unused_mismatch630(db_engine, keep_id, remove_id):
    if (type(keep_id) is not int or type(remove_id) is not int or
            keep_id < 1 or remove_id < 1 or keep_id == remove_id):
        raise ValueError("Invalid saved-food selection")
    food_bundle376.init_schema(db_engine)
    with db_engine.begin() as db:
        rows = [db.execute(text("""
            SELECT id,name,barcode,serving_description,nutrients
            FROM tracker_food_products WHERE id=:id
        """), {"id": id_}).mappings().first() for id_ in (keep_id, remove_id)]
        if any(row is None for row in rows):
            raise ValueError("Saved food changed or was removed")
        keeper, redundant = rows
        same_name = normalize629(keeper["name"]) == normalize629(redundant["name"])
        same_barcode = (normalize629(keeper["barcode"]) and
                        normalize629(keeper["barcode"]) == normalize629(redundant["barcode"]))
        if not (same_name or same_barcode):
            raise ValueError("These records are not direct duplicate candidates")
        used = db.execute(text("""
            SELECT COUNT(*) FROM tracker_food_entries WHERE product_id=:id
        """), {"id": remove_id}).scalar_one()
        if used:
            raise ValueError("Cannot remove a version referenced by historical meals")
        db.execute(text("""
            INSERT OR IGNORE INTO tracker_food_favorites(product_id)
            SELECT :keep FROM tracker_food_favorites WHERE product_id=:old
        """), {"keep": keep_id, "old": remove_id})
        db.execute(text("""
            DELETE FROM tracker_food_favorites WHERE product_id=:old
        """), {"old": remove_id})
        db.execute(text("""
            UPDATE tracker_food_meal_template_items SET product_id=:keep
            WHERE product_id=:old
        """), {"keep": keep_id, "old": remove_id})
        db.execute(text("""
            DELETE FROM tracker_food_products WHERE id=:old
        """), {"old": remove_id})
    return 1



def reassign_logged_uses641(db_engine, keep_id, remove_id, expected_count):
    """Repoint all logged meals from one duplicate to a chosen keeper.

    Dates, meals, serving quantities, entry IDs and other product versions stay
    intact. Historical nutrient totals are intentionally recalculated using
    the chosen keeper. The submitted expected count prevents stale approvals.
    """
    if (type(keep_id) is not int or type(remove_id) is not int or
            keep_id <= 0 or remove_id <= 0 or keep_id == remove_id or
            type(expected_count) is not int or
            not 1 <= expected_count <= 1000000):
        raise ValueError("Invalid logged-food reassignment")
    food_bundle376.init_schema(db_engine)
    with db_engine.begin() as db:
        rows = [db.execute(text("""
            SELECT id,name,barcode,serving_description
            FROM tracker_food_products WHERE id=:id
        """), {"id": id_}).mappings().first()
                for id_ in (keep_id, remove_id)]
        if any(row is None for row in rows):
            raise ValueError("Saved food changed or was removed")
        keeper, redundant = rows
        same_name = normalize629(keeper["name"]) == normalize629(redundant["name"])
        barcode = normalize629(keeper["barcode"])
        same_barcode = bool(barcode and barcode == normalize629(redundant["barcode"]))
        if not (same_name or same_barcode):
            raise ValueError("Foods are not direct duplicate candidates")
        count = db.execute(text("""
            SELECT COUNT(*) FROM tracker_food_entries WHERE product_id=:id
        """), {"id": remove_id}).scalar_one()
        if count != expected_count:
            raise ValueError("Logged uses changed; reload before reassigning")
        result = db.execute(text("""
            UPDATE tracker_food_entries SET product_id=:keep
            WHERE product_id=:old
        """), {"keep": keep_id, "old": remove_id})
        if result.rowcount != count:
            raise ValueError("Logged uses changed while reassigning")
    return count


def merge_equivalent629(db_engine, keep_id, remove_ids):
    if (type(keep_id) is not int or keep_id < 1
            or type(remove_ids) is not list
            or not 1 <= len(remove_ids) <= MAX_MERGE
            or any(type(value) is not int or value < 1
                   for value in remove_ids)
            or len(set(remove_ids)) != len(remove_ids)
            or keep_id in remove_ids):
        raise ValueError("Invalid consolidation selection")

    food_bundle376.init_schema(db_engine)
    with db_engine.begin() as db:
        ids = [keep_id, *remove_ids]
        records = []
        for value in ids:
            row = db.execute(text("""
                SELECT id,name,barcode,serving_description,nutrients
                FROM tracker_food_products WHERE id=:id
            """), {"id": value}).mappings().first()
            if row is None:
                raise ValueError("Saved food was changed or removed")
            records.append(row)
        try:
            keys = [compatible_key629(row) for row in records]
        except ValueError:
            raise ValueError("Invalid nutrient data; cannot merge") from None
        if any(key != keys[0] for key in keys[1:]):
            raise ValueError(
                "Different nutrients, serving sizes or barcodes: "
                "review these versions instead of merging"
            )

        # All links are moved before removing old product rows, atomically.
        for old_id in remove_ids:
            db.execute(text("""
                INSERT OR IGNORE INTO tracker_food_favorites(product_id)
                SELECT :keep FROM tracker_food_favorites
                WHERE product_id=:old
            """), {"keep": keep_id, "old": old_id})
            db.execute(text("""
                DELETE FROM tracker_food_favorites WHERE product_id=:old
            """), {"old": old_id})
            db.execute(text("""
                UPDATE tracker_food_entries SET product_id=:keep
                WHERE product_id=:old
            """), {"keep": keep_id, "old": old_id})
            db.execute(text("""
                UPDATE tracker_food_meal_template_items SET product_id=:keep
                WHERE product_id=:old
            """), {"keep": keep_id, "old": old_id})
            db.execute(text("""
                DELETE FROM tracker_food_products WHERE id=:old
            """), {"old": old_id})
    return len(remove_ids)


@router.get("/food/duplicates")
def review_duplicate_foods629(
    request: Request,
    merged: int = 0,
    resolved: int = 0,
    reassigned: int = 0,
    show_reviewed: int = 0,
    db_engine=Depends(get_food_read_engine406),
):
    report = duplicate_groups629(db_engine, show_reviewed=show_reviewed == 1)
    return render(
        request, "food_duplicates629.html",
        **report, nutrients=food.NUTRIENTS,
        merged=max(0, min(merged, MAX_MERGE)),
        resolved=resolved == 1,
        reassigned=max(0, min(reassigned, 1000000)),
        show_reviewed=show_reviewed == 1,
    )


@router.post("/food/duplicates/merge")
async def merge_duplicate_foods629(
    request: Request,
    db_engine=Depends(get_food_read_engine406),
):
    form = await request.form()
    allowed_fields = {"keep_id", "remove_id", "csrf_token"}
    if (not {"keep_id", "remove_id"} <= set(form)
        or not set(form) <= allowed_fields
        or len(form.getlist("csrf_token")) > 1
        or len(form.getlist("keep_id")) != 1
        or not 1 <= len(form.getlist("remove_id")) <= MAX_MERGE
    ):
        raise HTTPException(422, "Invalid duplicate merge form")
    try:
        ids = [int(value) for value in form.getlist("remove_id")]
        keep_id = int(form["keep_id"])
        merged = merge_equivalent629(db_engine, keep_id, ids)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return RedirectResponse(
        f"/food/duplicates?merged={merged}",
        status_code=303,
    )


@router.post("/food/duplicates/resolve-unused")
async def resolve_unused_food630(
    request: Request,
    db_engine=Depends(get_food_read_engine406),
):
    """One pre-existing CSRF-protected route for removing or reassigning."""
    form = await request.form()
    reassign = "expected_count" in form
    allowed = {"keep_id", "remove_id", "csrf_token"}
    if reassign:
        allowed.add("expected_count")
    if (set(form) - allowed
            or len(form.getlist("keep_id")) != 1
            or len(form.getlist("remove_id")) != 1
            or len(form.getlist("csrf_token")) > 1
            or (reassign and len(form.getlist("expected_count")) != 1)):
        raise HTTPException(422, "Invalid food resolution form")
    try:
        if reassign:
            moved = reassign_logged_uses641(
                db_engine, int(form["keep_id"]), int(form["remove_id"]),
                int(form["expected_count"]),
            )
            return RedirectResponse(
                f"/food/duplicates?reassigned={moved}", status_code=303
            )
        remove_unused_mismatch630(
            db_engine, int(form["keep_id"]), int(form["remove_id"])
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return RedirectResponse("/food/duplicates?resolved=1", status_code=303)


@router.post("/food/duplicates/keep-distinct")
async def keep_distinct_food630(
    request: Request,
    db_engine=Depends(get_food_read_engine406),
):
    form = await request.form()
    if (set(form) - {"fingerprint", "csrf_token"}
            or len(form.getlist("fingerprint")) != 1
            or len(form.getlist("csrf_token")) > 1):
        raise HTTPException(422, "Invalid duplicate review form")
    try:
        mark_distinct630(db_engine, str(form["fingerprint"]))
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return RedirectResponse("/food/duplicates?resolved=1", status_code=303)
