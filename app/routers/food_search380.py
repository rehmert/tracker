"""Release 380: bounded, read-only food-name search via Open Food Facts."""

import json
import re
from math import isfinite
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as URLRequest, urlopen

from fastapi import APIRouter, HTTPException

router = APIRouter()

BASE_URL = "https://world.openfoodfacts.org/cgi/search.pl"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
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

    request = URLRequest(
        BASE_URL + "?" + parameters,
        headers={
            "User-Agent": (
                "TrackerFoodJournal/0.1 "
                "(personal-use; openfoodfacts.org)"
            ),
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=8) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)

        if len(raw) > MAX_RESPONSE_BYTES:
            raise HTTPException(
                502,
                "Food database returned too much data.",
            )

        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("Invalid database response")

    except HTTPException:
        raise
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        raise HTTPException(
            503,
            "Food-name search is temporarily unavailable. "
            "Try a barcode or manual entry.",
        )

    return {
        "query": query,
        "products": normalize_results(payload),
        "source": "Open Food Facts",
    }


@router.get("/food/search-name")
def food_name_search(q: str = ""):
    return search_food_name(q)
