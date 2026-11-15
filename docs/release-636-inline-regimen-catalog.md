# Release 636 — Catalog suggestions inside existing regimen forms

Base: DEV-qualified Release 635 commit `8258d2ac587fac26a8ca8af5f426167602dfce07`.

## User experience

Both existing **Add supplement or medication** and **Edit item** forms retain their normal fields and POST endpoints. Typing 2+ characters into the **Name** field makes a debounced, optional lookup in the selected **Type**. Choosing a result populates only Name, Ingredient, Strength and Form when the catalog actually supplies those values. It also puts a removable catalog source identifier in the existing Notes field, visible before Save. All fields remain editable.

No separate page or mandatory lookup. Manual entry works when there are no matches, when offline or when an API fails. No automatic dose, instructions, purpose, schedule, administration, or Food Journal mutation.

## Public sources

- Medication: NLM RxNorm `GET /REST/drugs.json?name=...`, then openFDA Drug NDC `GET /drug/ndc.json?search=...`.
- Supplements: NIH Dietary Supplement Label Database `GET /api/v9/browse-products/?method=by_keyword&q=...`.

These are **label/product matches**, not treatment recommendations. Choosing a DSLD supplement also requests its individual NIH label by ID and shows labeled serving size and multiple ingredient quantities in the existing Notes field (when available). Tracker does not reduce a multi-ingredient supplement to a misleading single-strength value.

Outbound HTTP requests run server-side against fixed HTTPS provider domains, with a 3-second per-request timeout, 350 KiB maximum JSON body, 8 maximum results and 15-minute in-process cache. Query range: 2–80 characters. Failure is reported in the form and does not block manual entry. Public queries reveal the typed search term to providers, not any saved regimen data.

No schema changes and no new client write routes. Auth and origin/CSRF controls remain inherited from the Tracker app. Existing item POSTs and audit behavior remain authoritative.

## Qualification

Focused isolated tests:

```bash
python -m pytest -q --tb=short tests/test_release636_regimen_catalog.py
```

The tests mock providers; they do not access public networks. Live provider coverage should be confirmed separately in a DEV manual smoke before approving promotion. Never automatically deploy PROD.
