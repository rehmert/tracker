# Stage 8 — Inventory audit coverage

Adds transactional audit events for purchased vial and supply creation, purchased supply edits/deletion, purchased vial deletion, blend creation, source vial transfers, and blend dose/waste draws. Audit rows are committed with the associated operation. No schema migration. Audit history is not retroactive.
