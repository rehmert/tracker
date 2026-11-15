"""Release 636: bounded, read-only catalog suggestions for existing regimen forms.

Public data is untrusted label terminology, not a dose or treatment plan.
The endpoint never saves remote content or sends a user's existing regimen.
"""
from __future__ import annotations

import json
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException

router = APIRouter()
_CACHE = {}
_LOCK = threading.Lock()
_TTL_SECONDS = 900
_MAX_RESULTS = 8
_MAX_BODY = 350_000
_HEADERS = {"Accept": "application/json", "User-Agent": "Tracker-RegimenCatalog/636"}

_RX = "https://rxnav.nlm.nih.gov/REST/drugs.json"
_FDA = "https://api.fda.gov/drug/ndc.json"
_DSLD = "https://dsld-dev-api.app.cloud.gov/api/v9/browse-products/"


def _clean(value, limit):
    return str(value or "").strip()[:limit]


def _fetch(url, params):
    """Use fixed HTTPS endpoints only; bounded response, timeout, and JSON."""
    target = url + "?" + urlencode(params)
    with urlopen(Request(target, headers=_HEADERS), timeout=3) as response:
        if response.status != 200:
            raise URLError("Catalog provider unavailable")
        raw = response.read(_MAX_BODY + 1)
        if len(raw) > _MAX_BODY:
            raise ValueError("Catalog response exceeds size limit")
        return json.loads(raw)


def _match(source, identifier, name, *, ingredient="", strength="", form="", brand=""):
    name = _clean(name, 160)
    if not name:
        return None
    return dict(
        source=source,
        source_id=_clean(identifier, 100),
        name=name,
        ingredient=_clean(ingredient, 160),
        strength=_clean(strength, 80),
        form=_clean(form, 60),
        brand=_clean(brand, 160),
    )


def _rxnorm(term):
    data = _fetch(_RX, {"name": term})
    matches = []
    for group in data.get("drugGroup", {}).get("conceptGroup", []):
        for entry in group.get("conceptProperties", []) or []:
            item = _match("RxNorm", entry.get("rxcui", ""), entry.get("name", ""))
            if item:
                matches.append(item)
    return matches[:_MAX_RESULTS]


def _openfda(term):
    # Escaped literal phrase: no caller-controlled query operators.
    phrase = re.sub(r'[^\w\s-]', ' ', term).strip()
    if not phrase:
        return []
    escaped = phrase.replace('"', "")
    query = f'brand_name:"{escaped}" OR generic_name:"{escaped}"'
    data = _fetch(_FDA, {"search": query, "limit": _MAX_RESULTS})
    matches = []
    for entry in data.get("results", []):
        ingredients = entry.get("active_ingredients") or []
        ingredient = ", ".join(str(i.get("name", "")) for i in ingredients if isinstance(i, dict))
        strength = "; ".join(str(i.get("strength", "")) for i in ingredients if isinstance(i, dict))
        match = _match(
            "openFDA", entry.get("product_ndc", ""),
            entry.get("brand_name") or entry.get("generic_name"),
            ingredient=ingredient or entry.get("generic_name", ""),
            strength=strength,
            form=entry.get("dosage_form", ""),
            brand=entry.get("brand_name", ""),
        )
        if match:
            matches.append(match)
    return matches


def _dsld(term):
    data = _fetch(_DSLD, {"method": "by_keyword", "q": term, "size": _MAX_RESULTS})
    matches = []
    for hit in data.get("hits", []):
        label = hit.get("_source") or {}
        if not isinstance(label, dict):
            continue
        match = _match(
            "NIH DSLD", hit.get("_id", ""),
            label.get("fullName", ""),
            brand=label.get("brandName", ""),
            # A supplement may have many ingredients; do not imply the first
            # is the whole formula or fabricate an ingredient strength.
        )
        if match:
            matches.append(match)
    return matches


def suggestions(kind, term):
    """Search in-memory with short TTL. A failed provider is not a blank catalog."""
    if kind not in ("medication", "supplement"):
        raise ValueError("Invalid catalog type")
    term = term.strip()
    if not 2 <= len(term) <= 80 or any(ord(c) < 32 for c in term):
        raise ValueError("Search for 2–80 printable characters")

    key = (kind, term.casefold())
    now = time.monotonic()
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] > now:
            return cached[1]

    providers = ((_rxnorm, _openfda) if kind == "medication" else (_dsld,))
    results, failures = [], []
    seen = set()
    for provider in providers:
        try:
            matches = provider(term)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            failures.append(provider.__name__.lstrip("_"))
            continue
        for match in matches:
            unique = (match["source"], match["source_id"] or match["name"].casefold())
            if unique in seen:
                continue
            seen.add(unique)
            results.append(match)
            if len(results) >= _MAX_RESULTS:
                break
        if len(results) >= _MAX_RESULTS:
            break
    response = {"results": results, "unavailable": failures}
    # Do not cache complete provider outages.
    if len(failures) < len(providers):
        with _LOCK:
            if len(_CACHE) > 500:
                _CACHE.clear()
            _CACHE[key] = (now + _TTL_SECONDS, response)
    return response


@router.get("/regimen/catalog/suggest")
def suggest_catalog(kind: str = "", q: str = ""):
    if kind not in ("medication", "supplement") or not 2 <= len(q.strip()) <= 80:
        raise HTTPException(status_code=422, detail="Enter a valid type and 2–80 character name")
    try:
        return suggestions(kind, q)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/regimen/catalog/supplement-label")
def supplement_label(label_id: str = ""):
    """Optional DSLD label enrichment after choosing a supplement suggestion."""
    if not re.fullmatch(r"[0-9]{1,12}", label_id):
        raise HTTPException(status_code=422, detail="Invalid DSLD label identifier")
    try:
        label = _fetch(
            "https://dsld-dev-api.app.cloud.gov/api/v9/label/" + label_id, {}
        )
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"available": False, "ingredients": "", "form": "", "serving": ""}
    if not isinstance(label, dict):
        return {"available": False, "ingredients": "", "form": "", "serving": ""}

    rows = label.get("ingredientRows") or []
    summary = []
    for row in rows[:40]:
        if not isinstance(row, dict):
            continue
        name = _clean(row.get("name"), 80)
        if not name:
            continue
        quantities = row.get("quantity") or []
        qty = quantities[0] if quantities and isinstance(quantities[0], dict) else {}
        amount = str(qty.get("quantity") or "").strip()
        unit = _clean(qty.get("unit"), 20)
        summary.append(name + (f" {amount} {unit}".rstrip() if amount and unit else ""))
    serving = ""
    sizes = label.get("servingSizes") or []
    if sizes and isinstance(sizes[0], dict):
        size = sizes[0]
        quantity = size.get("minQuantity")
        unit = _clean(size.get("unit"), 40)
        if quantity is not None and unit:
            serving = f"{quantity} {unit}"
    state = label.get("physicalState") or {}
    form = _clean(state.get("langualCodeDescription"), 60) if isinstance(state, dict) else ""
    return {
        "available": True,
        "ingredients": "; ".join(summary)[:1600],
        "form": form,
        "serving": serving[:80],
    }
