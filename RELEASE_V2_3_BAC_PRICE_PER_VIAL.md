# BAC water price per vial

The dedicated BAC water purchase form accepts a price **per vial** rather than per mL.
The exact purchase line total is stored as vial count × price per vial in `bulk_total_cents`; stock continues to be tracked and consumed in mL.
The purchase table shows the price per vial for these entries. Existing BAC water purchase entries remain unchanged.
To edit an existing BAC water entry, use the package-mode edit form and enter the **total line price** for all vials.
No schema migration is required.
