# Stage 4 — Reconciliation review and audit visibility

- Reconciliation now requires reviewing a calculated before/after quantity and reason before recording a supply adjustment.
- Server requires an explicit confirmation and checks the original expected quantity to reject stale submissions.
- Existing inventory adjustments and ChangeAudit records are retained.
- New read-only `/audit-history` page shows paginated existing audit events with record-type/action filters.
- Audit coverage is **partial**: only workflows already emitting ChangeAudit events are represented. This release does not claim comprehensive auditing.
- No schema changes, no removed routes.
- Browser validation and optimistic concurrency are safeguards, not a substitute for transactional locking under simultaneous writes.
