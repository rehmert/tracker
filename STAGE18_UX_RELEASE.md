# Stage 18 — Dose mutation serialization

- Acquire SQLite `BEGIN IMMEDIATE` before reading inventory in dose edit and delete routes.
- Return HTTP 409 on write contention rather than proceeding on stale inventory.
- Add HTTP/SQLite regression tests for editing, deleting, audit events, and rejected overdraw edits.
- No schema migration.

Limitations: does not add durable idempotency to edits/deletes, fault injection, or simultaneous-client stress tests.
