"""Release 380: bounded, read-only food-name search via Open Food Facts."""

import re
from math import isfinite
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException

from ..off_lookup494 import OFFFailure494, fetch_json494

router = APIRouter()

BASE_URL = "https://world.openfoodfacts.org/cgi/search.pl"
MODERN_URL = "https://search.openfoodfacts.org/search"
MAX_RESULTS = 15


def macro_preview(nutriments):
    """Only report reliable, explicitly labeled per-100g macro data."""
    if not isinstance(nutriments, dict):
        return {}

    mapping = {
        "energy": "energy-kcal_100g",
        "proteins": "proteins_100g",
        "carbohydrates": "carbohydrates_100g",
        "fat": "fat_100g",
    }

    preview = {}

    for key, upstream_key in mapping.items():
        raw = nutriments.get(upstream_key)

        if raw is None or isinstance(raw, bool):
            continue

        try:
            number = float(raw)
        except (ValueError, TypeError, OverflowError):
            continue

        if not isfinite(number) or not 0 <= number <= 100000:
            continue

        preview[key] = round(number, 2)

    return preview


def normalize_results(payload):
    """Return only usable product identifiers and short display fields."""
    products = payload.get("products", [])
    if not isinstance(products, list):
        return []

    result = []
    seen = set()

    for product in products:
        if not isinstance(product, dict):
            continue

        code = str(product.get("code") or "").strip()
        name = str(
            product.get("product_name")
            or product.get("product_name_en")
            or ""
        ).strip()

        if (
            not re.fullmatch(r"\d{8,14}", code)
            or not name
            or code in seen
        ):
            continue

        seen.add(code)

        brand = str(product.get("brands") or "").strip()
        serving = str(
            product.get("serving_size") or ""
        ).strip()

        macro = macro_preview(product.get("nutriments"))

        result.append({
            "barcode": code,
            "name": name[:160],
            "brand": brand[:100],
            "serving": serving[:80],
            "macro_100g": macro,
            "nutrition_available": bool(macro),
            "nutrition_basis": "per 100 g",
        })

        if len(result) >= MAX_RESULTS:
            break

    return result


def search_food_name(query):
    query = str(query or "").strip()

    if not 2 <= len(query) <= 80:
        raise HTTPException(
            422,
            "Enter a food name containing 2–80 characters.",
        )

    parameters = urlencode({
        "search_terms": query,
        "search_simple": "1",
        "action": "process",
        "json": "1",
        "page_size": str(MAX_RESULTS),
        "page": "1",
        "fields": (
            "code,product_name,product_name_en,"
            "brands,serving_size,nutriments"
        ),
    })

    legacy_url = BASE_URL + "?" + parameters

    try:
        # The legacy search still covers more recently added products.
        # Never retry its 503 immediately: the modern service is a better
        # fallback and has an independent upstream infrastructure.
        payload = fetch_json494(
            legacy_url, "name-legacy", timeout=7, ttl=900, retry=False,
        )
        products = normalize_results(payload)
    except OFFFailure494 as legacy_failure:
        modern_parameters = urlencode({
            "q": query,
            "page_size": str(MAX_RESULTS),
            "page": "1",
            # The search index may not hold nutrition data; users fetch
            # complete serving details via the existing barcode endpoint.
            "fields": "code,product_name,brands,serving_size",
        })
        try:
            modern = fetch_json494(
                MODERN_URL + "?" + modern_parameters,
                "name-modern", timeout=7, ttl=900, retry=True,
            )
            hits = modern.get("hits")
            if not isinstance(hits, list):
                raise OFFFailure494("bad_search_response")
            # Search-a-licious returns product fields directly in hits.
            # Accept an Elasticsearch-style wrapper defensively as well.
            products = normalize_results({
                "products": [
                    item.get("_source", item)
                    if isinstance(item, dict) else item
                    for item in hits
                ]
            })
        except OFFFailure494 as modern_failure:
            limited = (
                legacy_failure.reason in ("rate_limited", "local_limit", "cooldown")
                and modern_failure.reason in ("rate_limited", "local_limit", "cooldown")
            )
            if limited:
                delay = max(
                    1,
                    min(120, max(
                        legacy_failure.retry_after or 1,
                        modern_failure.retry_after or 1,
                    )),
                )
                raise HTTPException(
                    429,
                    "Food search is busy. Please retry in a minute, "
                    "or enter the food manually.",
                    headers={"Retry-After": str(delay)},
                ) from None
            raise HTTPException(
                503,
                "Open Food Facts search is temporarily unavailable. "
                "Try a barcode or manual entry.",
            ) from None

    return {
        "query": query,
        "products": products,
        "source": "Open Food Facts",
    }


@router.get("/food/search-name")
def food_name_search(q: str = ""):
    return search_food_name(q)
