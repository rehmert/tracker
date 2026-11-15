# Release 639 — Structured medication and supplement product facts

Baseline: DEV-qualified Release 638, commit `94bf84d61410bb9cf9be2bc150f0e8f6114e83a2`.

## User-facing behavior

The existing **Add supplement or medication** and **Edit item** forms retain their original POST endpoints. Selecting NIH DSLD loads labeled manufacturer, serving quantity/unit, individual ingredient name, amount, unit, serving basis, percent Daily Value (where reported), other ingredients, servings per container and UPC, in a reviewable in-form table. Fields remain manually editable. The user can add/remove ingredient rows and explicitly choose manual facts if the selected label is incomplete.

Choosing RxNorm/openFDA also persists source, identifier and brand in the new facts table while continuing to use the existing product name, strength and form fields. The application's scheduling, prescribed directions, dose/administration logging, food journal and vial inventory remain separate and unchanged.

Unavailable/ambiguous label records do not silently populate incorrect values. Delayed network responses must not overwrite manual edits. When a product name changes, existing ingredient rows remain but the previous source relationship is cleared; nothing is deleted merely by searching.

## Reviewed additive schema

One new table, `regimen_product_facts639`, with a unique indexed FK to `regimen_items635.id`. The table persists structured JSON arrays of ingredient records, serving basis, percent Daily Value, brand, source, source ID, import timestamp, servings per container, UPC and other ingredients. This is **structured JSON in SQLite**, not one relational table per nutrient. No existing table, dose history, recorded amount or schedule is altered.

The existing release worker requires `--reviewed-facts-639 --db-migration`, its dedicated append-only schema reviewer, a verified SQLite backup plus isolated restore check, and all ordinary qualification and runtime gates. PROD must never be updated before exact-commit DEV review/approval.

## Qualification

1. Isolated HTTP persistence and reload: `tests/test_release639_supplement_facts.py`
2. API normalization: `tests/test_release636_regimen_catalog.py`
3. Chromium end-to-end Add/Edit form: `tests/browser/test_regimen_facts639_ui.py`, plus `test_regimen_catalog638_ui.py`
4. Live NIH lookup: search Nutrient 950, choose an actual label ID, retrieve and review servings and individual ingredient quantities. Results depend on NIH label completeness.
5. JS syntax: Node `--check` on the two affected scripts.
6. Guarded DEV installation and manual in-browser confirmation of persistence after save/reload.

**Safety:** manufacturer serving and %DV are label data, not personal dose recommendations. No intake is automatically recorded. If the supplier provides multiple ambiguous serving bases or nested blends that cannot be represented faithfully, the API flags the label as incomplete and the form blocks automatic save until explicitly switched to manual entry.
