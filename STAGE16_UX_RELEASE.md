# Stage 16 — Inventory Integrity Regression Suite

Adds six SQLite-backed integration tests for purchase and supply replay, conflicting token reuse, stale reconciliation, audit consistency, rollback atomicity, and competing writer reservations. Fixes a Stage 15 bug where replaying purchased vials, BAC water, or supplies referenced an undefined `back` variable and returned an exception instead of the intended replay notice. No schema changes.

Limitations: tests do not yet cover full browser flows, dose/blend route replay, or high-load multi-process stress testing.
