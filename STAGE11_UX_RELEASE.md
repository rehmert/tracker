# Stage 11 — Dose submission concurrency safeguards

- SQLite `BEGIN IMMEDIATE` reserves the write lock before vial inventory is read and validated during dose creation. Concurrent dose submissions cannot both pass based on stale remaining inventory.
- The dose form disables Add to log while its HTMX request is in flight and restores it after completion or HTTP error.
- No schema changes. Existing records unaffected.
- Scope: dose creation only. This is not a general idempotency-token implementation; repeated submissions after a completed request can still create distinct entries when inventory permits.
