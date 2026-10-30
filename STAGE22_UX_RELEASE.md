# Stage 22 — Purchased Inventory & Reconciliation Concurrency

Test-only release. Adds five concurrent HTTP integration tests for purchased vial additions, BAC water, purchased supplies, supply usage, and reconciliation stale-count protection. Uses the temporary SQLite isolation from Stage 20. No production code, schema, or service restart required. Run tests using `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_stage22_inventory_concurrency.py`.
