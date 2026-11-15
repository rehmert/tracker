# Release 634 — correct the compound assigned to one or multiple vials

## User workflow

- Individual vial: open its detail page, choose the correct **Compound** from the edit form and save. Existing forms without the new field remain supported.
- Bulk vials: select inventory rows, open **Bulk edit selected**, choose **Compound**, select **Set to value**, select the new compound and use the existing server preview and confirmation dialog.
- The bulk preview shows both the current and proposed **compound names**, not just numeric IDs.

## Safety contract

Reassignment is a correction to the vial's identity, not a new administration or inventory purchase. It updates only `vials.compound_id`. It does not change stored quantity, content unit, reconstitution volume, dose entries, purchase costs, lot, statuses, labels or other fields unless those are separately selected in the ordinary edit form.

Before mutation, the destination must exist, and the vial's recorded unit must have the same dimension as the destination compound's primary unit. Changing mass to IU or IU to mass is prohibited. Changing an already dosed vial, a vial used in a physical blend, or one with a primary or linked COA is prohibited; review those records first. No existing dose or blend interpretation is rewritten and no linked COA is silently reassigned.

An individual change is recorded as `ChangeAudit.action=compound_reassign` with before/after IDs. Bulk changes use the existing `bulk_update` per-vial audit entry, optimistic preview snapshot, inventory write reservation and single-transaction commit. The entire batch fails if any selected vial cannot be reassigned. A no-op does not create an audit entry.

## Focused validation

```bash
/opt/tracker/.venv/bin/python -m pytest -q --tb=short --maxfail=1 \
    tests/test_release634_vial_compound.py \
    tests/test_bulk_vial_stage5.py \
    tests/test_bulk_vial_transactions.py \
    tests/test_bulk_editor_filter_coordination.py \
    tests/test_bulk_field_finder.py \
    tests/test_bulk_review_shortcuts.py
```

No database schema change, global CSRF change or automatic production deployment. A user-facing DEV review should verify the list selection, preview names, individual vial picker and clear error messages. The PROD deployment remains a separate signed promotion.
