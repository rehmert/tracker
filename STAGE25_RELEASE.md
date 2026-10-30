# Tracker Stage 25 — Inventory Health diagnostics

Read-only supply-ledger estimate (for supplies without physical-count adjustments), missing purchase/supply/vial/dose references, invalid usage quantities and invalid adjustment values. No schema migrations. Does not change inventory.

Validation: 9 targeted tests passed. Full suite: 216 passed, 3 failed (legacy reconciliation test sends an invalid form; vendor bulk tests expect an older CSV format). Duplicate-token concurrent test passed, but this does not prove every submission route is race-free.

Apply this ZIP at /opt/tracker (archive paths are relative to application root). Back up the application and data first.
