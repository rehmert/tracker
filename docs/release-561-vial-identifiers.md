# Release 561 — Unique vial identifiers

Show permanent vial IDs in:
- The existing Vials inventory table
- The Blends source-vial dropdown

Format:
- Inventory: #ID · label, with lot beneath
- Blend selector: #ID · compound · label · lot · remaining

The database ID is the unique physical-vial reference.

No schema, status, transaction, dose, inventory,
or blend-calculation changes are made.

The existing table structure and dropdown option
values remain unchanged.
