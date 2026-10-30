# Stage 19 — Transaction failure and writer contention regression tests

This is a **test-only** release: no production code, schema, or UI changes.

Adds four HTTP/SQLite integration tests covering injected flush failure during dose creation (including durable replay token rollback), injected audit failure during dose editing and deletion, and locked-writer HTTP 409 responses for edits and deletion. Each verifies unchanged inventory after failure.

Run: `PYTHONPATH=. pytest -q tests/test_stage19_atomicity.py tests/test_stage18_dose_mutations.py tests/test_stage17_dose_blend_integrity.py`.

Limitations: SQLite-only, synchronous TestClient requests, no load testing or crash/power-loss simulation. Faults injected at ORM flush, not disk or commit failures.
