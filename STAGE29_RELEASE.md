# Stage 29 — Vial reconstitution transaction protection

- Reserve SQLite write transaction before loading vial and supply balances in the reconstitution POST handler.
- Prevent concurrent reconstitutions of the same vial from both passing the unconstituted check.
- Serialize BAC water and disposable stock checks against concurrent inventory writes.
- Reject NaN/infinite volume and invalid BAC water identifiers without a server error.
- No database migration. No existing data changed by patch installation.

Other vial edit, blend and reconciliation routes remain subject to further review.
