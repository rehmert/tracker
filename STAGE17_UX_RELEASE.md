# Stage 17 — Dose and blend integrity regression tests

- Fixed missing submission token in blend detail form, which disabled replay protection for normal browser draws.
- Included submitted supply selections and quantities in dose idempotency fingerprint to reject altered replay payloads.
- Added SQLite-backed HTTP integration tests for dose and blend replay, conflicting payloads, stock and audit conservation, failed-validation rollback, and competing SQLite writers.
- No schema changes.
- Legacy clients without tokens remain unprotected from replay.
