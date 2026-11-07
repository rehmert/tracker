"""Release 460: bounded Open Food Facts barcode lookup.

Public food metadata only. No Tracker database, session cookies,
private identifiers, write operation, or user-selected remote URL.
"""
import json
import math
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .secondary_nutrients463 import (
    NUTRIENTS, REMOTE_KEYS, OFF_MG, OFF_MCG
)

MAX_BYTES = 65536


class BarcodeUnavailable460(Exception):
    pass


class BarcodeNotFound460(Exception):
    pass


def validate_barcode460(value):
    if type(value) is not str or not re.fullmatch(
        r"[0-9]{8,14}", value
    ):
        raise ValueError("Enter an 8–14 digit barcode")
    return value


def number460(raw):
    if type(raw) not in (int, float):
        return None
    number = float(raw)
    if not math.isfinite(number) or not 0 <= number <= 100000:
        return None
    return round(number, 3)


def parse_product460(data, code):
    validate_barcode460(code)
    if type(data) is not dict:
        raise BarcodeUnavailable460()

    if data.get("status") != 1:
        raise BarcodeNotFound460()

    product = data.get("product")
    if type(product) is not dict:
        raise BarcodeUnavailable460()

    nutrients = product.get("nutriments")
    if type(nutrients) is not dict:
        nutrients = {}

    name = product.get("product_name")
    if type(name) is not str:
        name = ""
    name = name.strip()[:160] or "Unnamed product"

    serving = product.get("serving_size")
    if type(serving) is not str:
        serving = ""
    serving = serving.strip()[:80]

    # Never mix per-serving and per-100g figures.
    has_serving = any(
        number460(
            nutrients.get(REMOTE_KEYS[key] + "_serving")
        ) is not None
        for key in NUTRIENTS
    )
    suffix = "_serving" if has_serving else "_100g"

    values = {}
    for key in NUTRIENTS:
        raw = nutrients.get(REMOTE_KEYS[key] + suffix)

        if type(raw) not in (float, int):
            values[key] = None
            continue

        raw = float(raw)
        if not math.isfinite(raw) or raw < 0:
            values[key] = None
            continue

        multiplier = (
            1000 if key in OFF_MG
            else 1000000 if key in OFF_MCG
            else 1
        )

        value = round(raw * multiplier, 3)
        values[key] = (
            value if value <= 100000 else None
        )

    return {
        "barcode": code,
        "name": name,
        "basis": "per serving" if has_serving else "per 100 g",
        "serving": serving if has_serving else "100 g",
        "nutrients": values,
        "source": "Open Food Facts",
        "warning": (
            "Review product name, serving basis, and every value "
            "against the package before saving."
        ),
    }


def lookup_barcode460(code):
    validate_barcode460(code)

    url = (
        "https://world.openfoodfacts.org/api/v2/product/"
        + code
        + "?fields=product_name,serving_size,nutriments"
    )
    request = Request(
        url,
        headers={
            "User-Agent": (
                "TrackerFoodJournal/0.1 "
                "(personal-use; openfoodfacts.org)"
            ),
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=7) as response:
            raw = response.read(MAX_BYTES + 1)
    except (URLError, HTTPError, TimeoutError, OSError) as exc:
        raise BarcodeUnavailable460() from exc

    if len(raw) > MAX_BYTES:
        raise BarcodeUnavailable460()

    try:
        data = json.loads(raw.decode("utf-8", "strict"))
    except (UnicodeError, ValueError) as exc:
        raise BarcodeUnavailable460() from exc

    return parse_product460(data, code)
