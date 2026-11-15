#!/usr/bin/env python3
"""Release 636: bounded live catalog read-only smoke from the DEV host.

Use only in an isolated candidate worktree; no DB, credentials, or app writes.
"""
from app.routers import regimen_catalog636 as catalog

CASES = [
    ("RxNorm medication", "medication", "metformin", "RxNorm"),
    ("openFDA medication", "medication", "Tylenol", "openFDA"),
    ("NIH supplement", "supplement", "Vitamin D", "NIH DSLD"),
]


def main():
    success = True
    for label, kind, term, expected in CASES:
        print(f"=== {label} ({term}) ===", flush=True)
        try:
            result = catalog.suggestions(kind, term)
            sources = sorted(set(row["source"] for row in result["results"]))
            count = sum(row["source"] == expected for row in result["results"])
            print(f"MATCHES={len(result['results'])} SOURCES={sources} "
                  f"EXPECTED_SOURCE_MATCHES={count} "
                  f"PROVIDER_UNAVAILABLE={result['unavailable']}", flush=True)
            for row in result["results"][:3]:
                print(f"  {row['source']}: {row['name'][:100]}", flush=True)
            if expected in result["unavailable"] or count == 0:
                print("STATUS=FAIL_OR_INCOMPLETE", flush=True)
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
