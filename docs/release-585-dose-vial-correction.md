# Release 585 — change the vial assigned to a recorded dose

**Base:** PROD Release 584 `244b158980920fca4f4364d2048cc6a5c5fbbbf6`.

## User workflow

Open Dose Log > History > Edit on an existing single-vial dose.
A new **Vial used for this dose** picker shows the currently assigned
vial and eligible in-stock or in-use vials of the **same compound**,
including their permanent #ID, label, lot, status, and available
amount. The current vial is preserved as a choice even if closed or
finished. Save the correction in the existing form.

The audit view already shows before/after vial IDs; this release writes
the changed value as part of the existing dose correction audit.

## Inventory rules

The corrected DoseLog row is moved, not copied. Vial inventory is
calculated from linked DoseLog rows, so the original vial regains its
previously counted dose automatically and the destination vial loses
the corrected quantity. The destination receives an available-stock
credit for the original dose **only when it is the same vial**.

The destination must exist, match the original compound, be sealed or
in_use when different from the original, and have enough unconsumed
contents. The corrected amount is converted to base units using the
**destination** vial's concentration. This is particularly important
for a dose entered in mL. A previously sealed destination becomes
in_use after a successful correction. Other dose fields, manually
recorded supplies, and dose history remain editable as before.
A rejected correction rolls back the whole transaction.

This is for DoseLog entries associated with individual Vials. Blend
withdrawals are tracked separately and are not interchangeable.

## Regression coverage

`tests/test_release585_dose_vial_move.py` exercises the actual
HTTP edit flow against SQLite, with before/after stock verification
and a persisted audit. It tests moving back, mismatched compound,
missing vial, overdraw, and destination concentration conversion.
The complete existing backend and isolated browser suites remain
mandatory in the standard guarded DEV qualification.

## Deployment and remaining strict-CSRF work

No model/schema or dependency changes. No code installation, runtime
enforcement toggle, database migration, or external deployment is
performed by adding this release branch. Qualify through the signed
DEV-controlled promotion workflow before PROD.

The previously planned combined strict-CSRF work is deferred to
**Release 586–587** and remains report-only on installed DEV/PROD.
GitHub Issue #9 remains open.
