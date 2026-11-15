#!/usr/bin/env python3
"""Release 639: live read-only NIH Nutrient 950 structured-label acceptance."""
from app.routers import regimen_catalog636 as catalog


def main():
    items = catalog._dsld("Pure Encapsulations Nutrient 950")
    exact = [
        row for row in items
        if row["name"].strip().casefold() == "nutrient 950"
        and row["brand"].strip().casefold() == "pure encapsulations"
        and row["source_id"].isdigit()
    ]
    print("EXACT_NIH_LABELS=", len(exact), flush=True)
    qualified = []
    for row in exact[:5]:
        label_id = row["source_id"]
        data = catalog.supplement_label(label_id)
        rows = data.get("ingredient_rows", [])
        serving = data.get("serving", "")
        incomplete = bool(data.get("ingredient_rows_truncated"))
        print("LABEL_ID=", label_id,
              "SERVING=", repr(serving),
              "INGREDIENT_ROWS=", len(rows),
              "INCOMPLETE=", incomplete,
              "OTHER_INGREDIENTS=", bool(data.get("other_ingredients")),
              "UPC=", bool(data.get("upc_sku")),
              flush=True)
        if (data.get("available") and serving and
                len(rows) >= 10 and not incomplete and
                all(r.get("name") for r in rows)):
            qualified.append(label_id)
    print("IMPORTABLE_LABEL_IDS=", qualified, flush=True)
    if not qualified:
        print("RELEASE_639_LIVE_STRUCTURED_LABEL=FAILED")
        return 1
    print("RELEASE_639_LIVE_STRUCTURED_LABEL=PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
