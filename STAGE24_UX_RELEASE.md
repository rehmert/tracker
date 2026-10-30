# Stage 24 — Inventory Health Dashboard and Purchase Idempotency Regression

- Adds a read-only `/inventory-health` report using the Stage 23 consistency checker.
- Adds two tests verifying findings render and that viewing the report does not change inventory or audit history.
- Adds a deterministic purchase submission replay regression test.
- Does **not** change purchase write paths. The intermittent Stage 22 duplicate-token concurrency failure has not been proven resolved by this release; concurrent purchase races remain a known issue requiring reproduction and targeted correction.
- No database migration. A service restart is required to load the new route.
- Run `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_stage24_inventory_health.py tests/test_stage24_purchase_serialization.py tests/test_stage23_inventory_consistency.py`.
