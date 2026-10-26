# Tracker v2.3 — BAC water vial purchasing

- Adds a dedicated ingredient-free BAC water vial entry form to each purchase.
- Enter vial count and mL per vial; the resulting Supply is `kind=bac_water`, `compound_id=NULL`, and its purchased/remaining inventory is total mL.
- Existing preparation/reconstitution supply usage consumes this inventory without changes.
- Purchase and supply tables explicitly display supply units.
- No schema migration is required.
- Price entry is per mL, consistent with the existing Supply pricing model. Existing supply inventory and purchased items are unaffected.
- 120 automated tests passed.
