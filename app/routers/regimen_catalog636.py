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
    """Find supplement labels by product and brand, including multiword names.

    DSLD browse-by-keyword is not a reliable exact phrase search. Prefer
    quoted search-filter matches and fall back to one-word browse queries.
    """
    normalized = re.sub(r"[^a-z0-9]+", " ", term.casefold()).strip()
    tokens = normalized.split()
    # People commonly type brand followed by product, e.g.
    # "Pure Encapsulations Nutrient 950".
    product_phrase = (
        " ".join(tokens[-2:]) if len(tokens) > 2 and tokens[-1].isdigit()
        else " ".join(tokens)
    )
    queries = [product_phrase]
    if product_phrase != normalized:
        queries.append(normalized)
    rows = []
    seen = set()

    def include(data):
        for hit in (data.get("hits") or []):
            label = hit.get("_source") or {}
            if not isinstance(label, dict):
                continue
            match = _match(
                "NIH DSLD", hit.get("_id", ""),
                label.get("fullName", ""),
                brand=label.get("brandName", ""),
            )
            if match and (match["source_id"], match["name"]) not in seen:
                seen.add((match["source_id"], match["name"]))
                rows.append(match)

    errors = []
    for phrase in queries:
        try:
            include(_fetch(
                "https://dsld-dev-api.app.cloud.gov/api/v9/search-filter/",
                {"q": '"' + phrase + '"', "sort_by": "_score", "size": 32},
            ))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, KeyError):
            errors.append("search-filter")
        if rows:
            break

    if not rows:
        # Degrade to a product-name keyword, not an unbounded all-label query.
        keyword = tokens[-2] if len(tokens) > 1 and tokens[-1].isdigit() else tokens[-1]
        try:
            include(_fetch(_DSLD, {"method": "by_keyword", "q": keyword, "size": 64}))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError, KeyError):
            errors.append("browse-products")

    if not rows and len(errors) >= len(queries) + 1:
        raise URLError("NIH catalog provider unavailable")

    phrase_tokens = set(product_phrase.split())
    query_tokens = set(tokens)

    def rank(row):
        product = re.sub(r"[^a-z0-9]+", " ", row["name"].casefold()).strip()
        brand = re.sub(r"[^a-z0-9]+", " ", row["brand"].casefold()).strip()
        product_tokens = set(product.split())
        overlap = len(phrase_tokens & product_tokens)
        brand_overlap = len((query_tokens - phrase_tokens) & set(brand.split()))
        # Exact product and brand matches outrank broad keyword results.
        return (
            int(product == product_phrase),
            int(product_phrase in product),
            overlap,
            brand_overlap,
            -len(product),
        )

    rows = [row for row in rows if phrase_tokens & set(
        re.sub(r"[^a-z0-9]+", " ", row["name"].casefold()).split())]
    rows.sort(key=rank, reverse=True)
    return rows[:_MAX_RESULTS]

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

    providers = (
        (("rxnorm", _rxnorm), ("openfda", _openfda))
        if kind == "medication" else (("dsld", _dsld),)
    )
    results, failures = [], []
    seen = set()
    for provider_name, provider in providers:
        try:
            matches = provider(term)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            failures.append(provider_name)
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
    if not isinstance(rows, list):
        rows = []
    ingredients = []
    truncated = len(rows) > 300
    for row in rows[:300]:
        if not isinstance(row, dict):
            continue
        name = _clean(row.get("name"), 160)
        if not name:
            continue
        quantities = row.get("quantity") or []
        if not isinstance(quantities, list):
            quantities = []
        if row.get("nestedRows"):
            # Hierarchical blends cannot be flattened accurately by this
            # simple table. Refuse a claim of complete import.
            truncated = True
        if len(quantities) > 8:
            truncated = True
        if not quantities:
            ingredients.append({
                "name": name, "amount": "", "unit": "",
                "basis": "", "daily_value": "",
            })
        else:
            for qty in quantities[:8]:
                if not isinstance(qty, dict):
                    continue
                targets = qty.get("dailyValueTargetGroup") or []
                dv = ""
                if isinstance(targets, list):
                    dv = "; ".join(
                        (str(t.get("name") or "") + ": " +
                         str(t.get("percent")) + "%").strip()
                        for t in targets if isinstance(t, dict)
                        and t.get("percent") is not None
                    )[:160]
                basis_quantity = qty.get("servingSizeQuantity")
                basis = (
                    (_clean(basis_quantity, 40) + " " +
                     _clean(qty.get("servingSizeUnit"), 60)).strip()
                    if basis_quantity is not None else ""
                )
                ingredients.append({
                    "name": name,
                    "amount": _clean(qty.get("quantity"), 40),
                    "unit": _clean(qty.get("unit"), 40),
                    "basis": basis,
                    "daily_value": dv,
                })
    if len(ingredients) > 300:
        truncated = True
        ingredients = ingredients[:300]
    sizes = label.get("servingSizes") or []
    if not isinstance(sizes, list):
        sizes = []
    size = sizes[0] if sizes and isinstance(sizes[0], dict) else {}
    quantity = size.get("minQuantity")
    serving_quantity = _clean(quantity, 40) if quantity is not None else ""
    serving_unit = _clean(size.get("unit"), 80)
    if len(sizes) == 1 and serving_quantity and serving_unit:
        default_basis = (serving_quantity + " " + serving_unit)[:100]
        for ingredient in ingredients:
            if not ingredient["basis"]:
                ingredient["basis"] = default_basis
    elif len(sizes) > 1 and any(not row["basis"] for row in ingredients):
        # Multiple serving bases: do not silently attach quantities to the
        # wrong serving size.
        truncated = True
    state = label.get("physicalState") or {}
    form = _clean(state.get("langualCodeDescription"), 60) if isinstance(state, dict) else ""
    others = label.get("otheringredients") or {}
    other_ingredients = _clean(others.get("text"), 4000) if isinstance(others, dict) else ""
    if isinstance(others, dict) and len(str(others.get("text") or "")) > 4000:
        truncated = True
    return {
        "available": True,
        "ingredients": "; ".join(
            (r["name"] + " " + r["amount"] + " " + r["unit"]).strip()
            for r in ingredients
        )[:1600],  # Legacy summary only, not persisted.
        "ingredient_rows": ingredients,
        "ingredient_rows_truncated": truncated,
        "form": form,
        "serving": (serving_quantity + " " + serving_unit).strip()[:80],
        "serving_quantity": serving_quantity,
        "serving_unit": serving_unit,
        "other_ingredients": other_ingredients,
        "servings_per_container": _clean(label.get("servingsPerContainer"), 80),
        "upc_sku": _clean(label.get("upcSku"), 80),
    }
