# Tracker UX Stage 5 — Transactional Audit Expansion

Adds transactionally recorded change history for purchase creation, header edits, deletion, and protocol creation, full edits, date changes, activation, duplication, and deletion. All audit records are inserted in the same SQLAlchemy transaction as the underlying change, so failed commits do not leave false audit entries. Protocol snapshots include schedule items. Purchase snapshots include header fields but not child vial/supply changes; those remain future work. Existing audit-history page displays these events. No schema changes.

## Limitations
- Not comprehensive coverage of all inventory-changing endpoints.
- Audit history may contain sensitive purchase notes.
- Does not retroactively record past edits.
- Must be tested against a copy of the production database before live deployment.
