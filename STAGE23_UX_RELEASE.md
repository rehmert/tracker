# Stage 23 — Read-only Inventory Consistency Diagnostics

Adds `app/inventory_consistency.py` with a read-only diagnostic function and four isolated SQLite tests. For supplies, it compares stored remaining quantity to purchased quantity minus recorded usage plus reconciliation deltas. Flags negative/non-finite quantities and invalid usage amounts. For vials, checks recorded dose and blend-transfer consumption for non-finite/negative totals, but deliberately does not reconstruct potency-adjusted balances.

**Limitations:** historical edits, direct stock adjustments, imports, deletions and missing transactions can produce false mismatches. Findings are review prompts, not automatic corrections. No UI, scheduled checks, production write paths, or database migrations are added.

Run: `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_stage23_inventory_consistency.py`
