"""Mobile-first food journal. Nutrient values are user-reviewable, never clinical diagnoses."""
import json
import re
import shutil
import subprocess
from datetime import date, timedelta
from ..off_lookup494 import OFFFailure494, fetch_json494
from fastapi import Depends, APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import text
from ..db import engine
from ..templating import render

from ..food_storage_guard391 import require_food_storage391
from ..food_read_engine406 import get_food_read_engine406
from ..food_water425 import (
    init_water_schema, water_report, parse_ounces,
)

router = APIRouter(
    dependencies=[Depends(require_food_storage391)]
)
# Units are intentionally explicit. Sodium, potassium and calcium are mg; iron is mg.
NUTRIENTS = {
    "energy": ("Calories", "kcal"), "proteins": ("Protein", "g"),
    "carbohydrates": ("Carbs", "g"), "fat": ("Fat", "g"),
    "fiber": ("Fiber", "g"), "sugars": ("Sugar", "g"),
    "saturated-fat": ("Saturated Fat", "g"),
    "sodium": ("Sodium", "mg"), "potassium": ("Potassium", "mg"),
    "calcium": ("Calcium", "mg"), "iron": ("Iron", "mg"),
    "magnesium": ("Magnesium", "mg"), "vitamin-c": ("Vitamin C", "mg"),
    "vitamin-d": ("Vitamin D", "mcg"), "vitamin-b12": ("Vitamin B12", "mcg"),
    "cholesterol": ("Cholesterol", "mg"),
}
# Open Food Facts generally expresses salt/sodium and minerals in grams.
OFF_MG = {"sodium", "potassium", "calcium", "iron", "magnesium", "vitamin-c", "cholesterol"}
OFF_MCG = {"vitamin-d", "vitamin-b12"}

# Weekly summaries need the six preceding days; navigation needs the next day.
EARLIEST_FOOD_DAY = date.min + timedelta(days=6)
LATEST_FOOD_DAY = date.max - timedelta(days=1)


def require_supported_food_day(chosen: date) -> date:
    """Reject dates that would overflow the journal's calendar calculations."""
    if not EARLIEST_FOOD_DAY <= chosen <= LATEST_FOOD_DAY:
        raise HTTPException(422, "Day is outside the supported navigation range")
    return chosen


def init_food_schema(db_engine=None):
    selected_engine = engine if db_engine is None else db_engine
    with selected_engine.begin() as db:
        db.exec_driver_sql("""CREATE TABLE IF NOT EXISTS tracker_food_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT, barcode TEXT,
            name TEXT NOT NULL, serving_description TEXT NOT NULL,
            nutrients TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'manual',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        db.exec_driver_sql("""CREATE TABLE IF NOT EXISTS tracker_food_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL,
            eaten_on TEXT NOT NULL, meal TEXT NOT NULL, servings REAL NOT NULL,
            FOREIGN KEY(product_id) REFERENCES tracker_food_products(id))""")
        db.exec_driver_sql("""CREATE TABLE IF NOT EXISTS tracker_food_targets (
            nutrient TEXT PRIMARY KEY, value REAL NOT NULL)""")

        db.exec_driver_sql("""CREATE TABLE IF NOT EXISTS tracker_food_favorites (
            product_id INTEGER PRIMARY KEY,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES tracker_food_products(id))""")

def optional_nutrient(raw):
    """Preserve unknown separately from a confirmed numeric zero."""
    if raw is None or str(raw).strip() == "":
        return None
    try:
        from math import isfinite
        value = float(raw)
    except (ValueError, TypeError, OverflowError):
        raise HTTPException(422, "Invalid nutrient value")
    if not isfinite(value) or value < 0 or value > 100000:
        raise HTTPException(422, "Nutrient value is out of range")
    return value

def nutrient_coverage(day, db_engine=None):
    """Count foods with reported values, independently per nutrient."""
    selected_engine = engine if db_engine is None else db_engine
    with selected_engine.connect() as db:
        records = db.execute(text("""
            SELECT p.nutrients FROM tracker_food_entries e
            JOIN tracker_food_products p ON p.id=e.product_id
            WHERE e.eaten_on=:day
        """), {"day": day}).all()
    counts = {key: 0 for key in NUTRIENTS}
    for (raw,) in records:
        values = json.loads(raw)
        for key in NUTRIENTS:
            if values.get(key) is not None:
                counts[key] += 1
    return counts, len(records)

def to_float(raw):
    try:
        val = float(raw or 0)
        return val if 0 <= val <= 100000 else 0.0
    except (TypeError, ValueError, OverflowError):
        return 0.0

def totals_for(day, db_engine=None):
    selected_engine = engine if db_engine is None else db_engine
    with selected_engine.connect() as db:
        records = db.execute(text("""SELECT p.nutrients,e.servings FROM tracker_food_entries e
           JOIN tracker_food_products p ON p.id=e.product_id WHERE e.eaten_on=:day"""), {"day":day}).all()
    return {k: round(sum(to_float(json.loads(n).get(k))*s for n,s in records),2) for k in NUTRIENTS}

@router.get("/food")
def food_page(
    request: Request,
    day: str = "",
    q: str = "",
    db_engine=Depends(get_food_read_engine406),
):
    try:
        chosen = date.fromisoformat(day) if day else date.today()
    except ValueError:
        chosen = date.today()
    chosen = require_supported_food_day(chosen)
    day = chosen.isoformat()
    # Invalid date requests must not initialize or access storage.
    init_food_schema(db_engine)
    init_water_schema(db_engine)
    with db_engine.connect() as db:
        records = db.execute(text("""SELECT e.id, p.id AS product_id, p.name,p.serving_description,p.nutrients,
            e.servings,e.meal,p.source FROM tracker_food_entries e JOIN tracker_food_products p
            ON p.id=e.product_id WHERE e.eaten_on=:d ORDER BY e.id DESC"""),{"d":day}).mappings().all()
        targets = dict(db.execute(text("SELECT nutrient,value FROM tracker_food_targets")).all())
    rows = [dict(r) for r in records]
    total = totals_for(day, db_engine=db_engine)
    water = water_report(day, db_engine)
    coverage, food_count = nutrient_coverage(
        day, db_engine=db_engine
    )
    from .food_quick375 import saved_foods
    favorites, recent = saved_foods(
        db_engine=db_engine
    )
    favorite_ids = {item["id"] for item in favorites}
    from .food_bundle376 import (
        search_products, weekly_summary, meal_templates
    )
    query = q.strip()[:100]
    search_results = (
        search_products(query, db_engine=db_engine)
        if query else []
    )
    week = weekly_summary(day, db_engine=db_engine)
    templates = meal_templates(db_engine=db_engine)
    from .food_review378 import meal_summary
    meals = meal_summary(day, db_engine=db_engine)
    from .food_week379 import week_details
    nutrient_week = week_details(day, db_engine=db_engine)
    for row in rows:
        row["parsed_nutrients"] = json.loads(row["nutrients"])

    from .food_preview384 import attach_previews
    attach_previews(rows)
    attach_previews(favorites)
    attach_previews(recent)
    attach_previews(search_results)

    return render(
        request, "food.html", day=day, entries=rows,
        nutrients=NUTRIENTS, totals=total, targets=targets,
        coverage=coverage, food_count=food_count,
        water=water,
        favorites=favorites, recent=recent,
        favorite_ids=favorite_ids,
        search_query=query, search_results=search_results,
        week=week, templates=templates,
        meals=meals, nutrient_week=nutrient_week,
        previous_day=(chosen - timedelta(days=1)).isoformat(),
        next_day=(chosen + timedelta(days=1)).isoformat(),
        today=date.today().isoformat(),
    )


@router.post("/food/water")
async def add_water425(
    request: Request,
    db_engine=Depends(get_food_read_engine406),
):
    """Record drinking water for the selected Food Journal day."""
    from .food_quick375 import selected_day

    form = await request.form()
    day = selected_day(form.get("day"))

    try:
        ounces = parse_ounces(form.get("ounces"))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    init_water_schema(db_engine)

    with db_engine.begin() as db:
        db.execute(text("""
            INSERT INTO tracker_water_entries(logged_on, ounces)
            VALUES (:day, :ounces)
        """), {"day": day, "ounces": ounces})

    return RedirectResponse(
        "/food?day=" + day + "#food-water",
        status_code=303,
    )


@router.post("/food/water/{entry_id}/delete")
async def delete_water425(
    entry_id: int,
    request: Request,
    db_engine=Depends(get_food_read_engine406),
):
    """Delete only an entry belonging to the submitted day."""
    from .food_quick375 import selected_day

    form = await request.form()
    day = selected_day(form.get("day"))

    if entry_id <= 0:
        raise HTTPException(404, "Water entry not found")

    init_water_schema(db_engine)

    with db_engine.begin() as db:
        result = db.execute(text("""
            DELETE FROM tracker_water_entries
            WHERE id=:id AND logged_on=:day
        """), {"id": entry_id, "day": day})

        if result.rowcount != 1:
            raise HTTPException(404, "Water entry not found")

    return RedirectResponse(
        "/food?day=" + day + "#food-water",
        status_code=303,
    )


@router.get("/food/barcode/{barcode}")
def barcode_lookup(barcode: str):
    if not re.fullmatch(r"\d{8,14}",barcode):
        raise HTTPException(400,"Enter a valid 8–14 digit barcode.")
    url=f"https://world.openfoodfacts.org/api/v2/product/{barcode}?fields=product_name,brands,serving_size,nutriments"
    try:
        payload=fetch_json494(
            url, "barcode", timeout=7, ttl=3600, retry=True,
        )
    except OFFFailure494 as exc:
        if exc.reason == "not_found":
            raise HTTPException(
                404, "Barcode not found. Verify the code or enter manually.",
            ) from None
        if exc.reason in ("rate_limited", "local_limit", "cooldown"):
            raise HTTPException(
                429,
                "Food database is busy. Retry shortly or enter label details manually.",
                headers={"Retry-After": str(min(120, exc.retry_after or 60))},
            ) from None
        raise HTTPException(
            503, "Food database temporarily unavailable. Enter label details manually.",
        ) from None
    if payload.get("status")!=1:
        raise HTTPException(404,"Barcode not found. Use a nutrition-label photo or manual entry.")
    p=payload.get("product") or {}
    info=p.get("nutriments") or {}
    serving=p.get("serving_size") or ""
    # Prefer values per stated serving. Otherwise use known 100g basis, never
    # silently treat 100g data as package serving.
    use_serving=bool(info.get("energy-kcal_serving") is not None or info.get("proteins_serving") is not None)
    suffix="_serving" if use_serving else "_100g"
    serving_grams = None
    match = re.fullmatch(
        r"\s*(\d+(?:\.\d+)?)\s*g\s*",
        str(serving), re.I
    )
    if match:
        serving_grams = float(match.group(1))
    amounts={}
    for key in NUTRIENTS:
        offkey="energy-kcal" if key=="energy" else key
        raw=info.get(offkey+suffix)
        if raw is None and use_serving and serving_grams is not None:
            per_100g = info.get(offkey+"_100g")
            if per_100g is not None:
                raw = to_float(per_100g) * serving_grams / 100
        if raw is None: continue
        multiplier=1000 if key in OFF_MG else 1000000 if key in OFF_MCG else 1
        amounts[key]=round(to_float(raw)*multiplier,3)
    name=(p.get("product_name") or "Unnamed product").strip()[:160]
    return {"barcode":barcode,"name":name,"serving_description": serving if use_serving and serving else "100 g",
            "nutrients":amounts,"source":"Open Food Facts; verify against packaging",
            "basis":"per stated serving" if use_serving else "per 100 g"}

@router.post("/food/photo")
async def label_photo(photo: UploadFile=File(...)):
    data=await photo.read(5*1024*1024+1)
    if len(data)>5*1024*1024:
        raise HTTPException(413,"Photo must be 5 MB or less.")
    if not (data.startswith(b"\xff\xd8\xff") or data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"RIFF") and data[8:12]==b"WEBP"):
        raise HTTPException(415,"Upload JPEG, PNG or WebP.")
    if not shutil.which("tesseract"):
        return JSONResponse({"error":"OCR unavailable on server: install tesseract-ocr. You can still type the label."},status_code=503)
    ext="jpg" if data.startswith(b"\xff\xd8") else "png" if data.startswith(b"\x89PNG") else "webp"
    import tempfile, os
    path=None
    try:
        with tempfile.NamedTemporaryFile(suffix="."+ext,delete=False) as tmp:
            tmp.write(data)
            path=tmp.name
        proc=subprocess.run(["tesseract",path,"stdout","-l","eng"],
              capture_output=True,text=True,timeout=15,check=False)
        raw=proc.stdout[:12000] if proc.returncode==0 else ""
    except (OSError,subprocess.TimeoutExpired):
        raw=""
    finally:
        if path:
            try: os.unlink(path)
            except OSError: pass
    if not raw.strip():
        return JSONResponse({"error":"No readable nutrition text detected. Retake the photo in good light, or enter manually."},status_code=422)
    patterns={
        "energy":r"(?:calories|energy)\s*[: ]\s*(\d+(?:\.\d+)?)",
        "proteins":r"protein\s*[: ]\s*(\d+(?:\.\d+)?)",
        "carbohydrates":r"(?:total\s*)?carbohydrates?\s*[: ]\s*(\d+(?:\.\d+)?)",
        "fat":r"total\s*fat\s*[: ]\s*(\d+(?:\.\d+)?)",
        "saturated-fat":r"saturated\s*fat\s*[: ]\s*(\d+(?:\.\d+)?)",
        "fiber":r"(?:dietary\s*)?fib(?:er|re)\s*[: ]\s*(\d+(?:\.\d+)?)",
        "sugars":r"(?:total\s*)?sugars?\s*[: ]\s*(\d+(?:\.\d+)?)",
        "sodium":r"sodium\s*[: ]\s*(\d+(?:\.\d+)?)",
        "potassium":r"potassium\s*[: ]\s*(\d+(?:\.\d+)?)",
        "calcium":r"calcium\s*[: ]\s*(\d+(?:\.\d+)?)",
        "iron":r"iron\s*[: ]\s*(\d+(?:\.\d+)?)",
        "cholesterol":r"cholesterol\s*[: ]\s*(\d+(?:\.\d+)?)",
    }
    amounts={}
    for key,pattern in patterns.items():
        match=re.search(pattern,raw,re.I)
        if match: amounts[key]=to_float(match.group(1))
    return {"nutrients":amounts,"raw_text":raw[:2000],
            "warning":"OCR is tentative; check the serving size, units and every value before saving."}

@router.post("/food/entry")
async def create_food_entry(request: Request, db_engine=Depends(get_food_read_engine406)):
    init_food_schema(db_engine)
    form=await request.form()
    name=str(form.get("name","")).strip()[:160]
    if not name:
        raise HTTPException(422,"Food name is required.")
    eaten=str(form.get("day",""))
    try:
        chosen = date.fromisoformat(eaten)
    except ValueError:
        raise HTTPException(422, "Invalid date") from None
    require_supported_food_day(chosen)
    quantity=to_float(form.get("servings"))
    if not 0 < quantity <= 100:
        raise HTTPException(422,"Servings must be greater than zero and at most 100.")
    meal=str(form.get("meal","Snack"))
    if meal not in ("Breakfast","Lunch","Dinner","Snack"): meal="Snack"
    info={key:optional_nutrient(form.get(key)) for key in NUTRIENTS}
    barcode=str(form.get("barcode","")).strip()
    if barcode and not re.fullmatch(r"\d{8,14}",barcode): barcode=""
    desc=str(form.get("serving_description","1 serving")).strip()[:80] or "1 serving"
    source=str(form.get("source","manual")).strip()[:80]
    nutrient_json = json.dumps(info)
    params = {
        "barcode": barcode, "name": name, "desc": desc,
        "nutrients": nutrient_json, "source": source
    }
    with db_engine.begin() as db:
        existing = db.execute(text("""
            SELECT id FROM tracker_food_products
            WHERE lower(name)=lower(:name)
              AND COALESCE(barcode,'')=:barcode
              AND serving_description=:desc
              AND source=:source
              AND nutrients=:nutrients
            ORDER BY id DESC LIMIT 1
        """), params).first()

        if existing:
            product_id = existing[0]
        else:
            result = db.execute(text("""
                INSERT INTO tracker_food_products
                    (barcode,name,serving_description,nutrients,source)
                VALUES (:barcode,:name,:desc,:nutrients,:source)
            """), params)
            product_id = result.lastrowid

        db.execute(text("""
            INSERT INTO tracker_food_entries
                (product_id,eaten_on,meal,servings)
            VALUES (:p,:d,:m,:s)
        """), {
            "p": product_id, "d": eaten,
            "m": meal, "s": quantity
        })
    return RedirectResponse(
        "/food?day=" + eaten + "#food-recorded",
        status_code=303,
    )

@router.post("/food/targets")
async def save_food_targets(request: Request, db_engine=Depends(get_food_read_engine406)):
    init_food_schema(db_engine)
    form=await request.form()
    day=str(form.get("day",date.today().isoformat()))
    from .food_quick375 import selected_day
    day = selected_day(day)

    validated = {}
    for key in NUTRIENTS:
        raw = str(form.get(key, "")).strip()
        validated[key] = (
            optional_nutrient(raw) if raw else None
        )

    with db_engine.begin() as db:
        for key, value in validated.items():
            if value is None:
                db.execute(text("""
                    DELETE FROM tracker_food_targets
                    WHERE nutrient=:key
                """), {"key": key})
            else:
                db.execute(text("""
                    INSERT INTO tracker_food_targets(nutrient,value)
                    VALUES (:key,:value)
                    ON CONFLICT(nutrient)
                    DO UPDATE SET value=excluded.value
                """), {"key": key, "value": value})
    return RedirectResponse("/food?day="+day,status_code=303)

@router.post("/food/entry/{entry_id}/delete")
async def delete_food_entry(entry_id: int, request: Request, db_engine=Depends(get_food_read_engine406)):
    init_food_schema(db_engine)
    form = await request.form()

    from .food_quick375 import selected_day, food_redirect
    day = selected_day(form.get("day"))

    with db_engine.begin() as db:
        result = db.execute(text("""
            DELETE FROM tracker_food_entries
            WHERE id=:id AND eaten_on=:day
        """), {"id": entry_id, "day": day})

        if result.rowcount != 1:
            raise HTTPException(404, "Food entry not found")

    return food_redirect(day, "food-recorded")
