#!/usr/bin/env python3
"""Release 636: bounded live catalog read-only smoke from the DEV host.

Use only in an isolated candidate worktree; no DB, credentials, or app writes.
"""
from app.routers import regimen_catalog636 as catalog

CASES = [
    ("RxNorm medication", catalog._rxnorm, "metformin", "RxNorm"),
    ("openFDA medication", catalog._openfda, "Tylenol", "openFDA"),
    ("NIH supplement", catalog._dsld, "Vitamin D", "NIH DSLD"),
]


def main():
    success = True
    for label, fetcher, term, expected in CASES:
        print(f"=== {label} ({term}) ===", flush=True)
        try:
            rows = fetcher(term)
            sources = sorted(set(row["source"] for row in rows))
            count = sum(row["source"] == expected for row in rows)
            print(f"MATCHES={len(rows)} SOURCES={sources} "
                  f"EXPECTED_SOURCE_MATCHES={count}", flush=True)
            for row in rows[:3]:
                print(f"  {row['source']}: {row['name'][:100]}", flush=True)
            if count == 0:
                print("STATUS=FAIL_OR_INCOMPLETE", flush=True)
                success = False
            else:
                print("STATUS=PASS", flush=True)
        except Exception as exc:
            print(f"STATUS=ERROR {type(exc).__name__}: {exc}", flush=True)
            success = False

    print("=== Exact Nutrient 950 lookup ===", flush=True)
    for query in ("Nutrient 950", "Pure Encapsulations Nutrient 950"):
        try:
            results = catalog.suggestions("supplement", query)
            labels = [(r["source_id"], r["name"], r["brand"]) for r in results["results"]]
            print(f"QUERY={query!r} MATCHES={len(labels)} TOP={labels[:3]}", flush=True)
            if not labels or labels[0][0] != "277968":
                print("STATUS=FAIL_EXACT_PRODUCT_NOT_FIRST", flush=True)
                success = False
            else:
                print("STATUS=PASS", flush=True)
        except Exception as exc:
            print(f"STATUS=ERROR {type(exc).__name__}: {exc}", flush=True)
            success = False

    print("=== NIH label 82118 ===", flush=True)
    try:
        detail = catalog.supplement_label("82118")
        print("AVAILABLE=", detail.get("available"),
              "SERVING=", detail.get("serving"),
              "INGREDIENT_CHARACTERS=", len(detail.get("ingredients", "")),
              "FORM=", detail.get("form"), flush=True)
        if not detail.get("available") or not detail.get("ingredients"):
            success = False
            print("STATUS=FAIL_OR_INCOMPLETE", flush=True)
        else:
            print("STATUS=PASS", flush=True)
    except Exception as exc:
        print(f"STATUS=ERROR {type(exc).__name__}: {exc}", flush=True)
        success = False
    print("RELEASE_636_LIVE_CATALOG=" + ("PASSED" if success else "FAILED"))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
