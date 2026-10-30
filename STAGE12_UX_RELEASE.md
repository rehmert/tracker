# Stage 12 — Serialized inventory writes

- Blend creation reserves SQLite write access **before** calculating source-vial availability.
- Blend dose/waste logging reserves SQLite write access **before** checking remaining volume.
- Physical supply reconciliation reserves SQLite write access **before** comparing the submitted expected stock count.
- Busy-database errors display a retry message without changing stock.
- Fixed blend completion calculation to compare the new draw with the **pre-draw** remaining volume.
- No schema migration. SQLite-specific protection; requires all competing inventory writers to follow this pattern.
- Does not implement durable idempotency keys or guarantee exactly-once submission.
