# Release 732 — Delete a medication

**Pinned DEV base:** Release 731 `0bc005f9c1e5b1353a67755aeeb2940140a7c74f`.

## Behavior

The medication's Catalog card now displays **Delete medication** next to
Edit and Archive. Available for active and archived medications.
A browser confirmation names the number of linked schedules and intake
records that will be deleted; cancel performs no POST. The server also
requires the explicit `confirm_delete=delete` form value.

Deletion is a scoped, atomic, audited operation. It removes exactly the
medication's catalog record, product facts, linked schedules and their
tablet plans, and linked intake records and their actual tablet snapshots.
The private ChangeAudit records are preserved. There are no automatic
food, injectable, vial or stock changes. This is permanent; Archive
remains available to retain full daily history instead.

The handler refuses deletion for supplements and fails closed if legacy
data associates another medication's intake with the target medication's
schedule. A missing record returns 404 and no record is deleted on GET.

## Scoped verification

- Disposable SQLite with foreign key enforcement, independent related
  and unrelated medications, actual dose snapshots and product facts.
- Cancel/no confirmation, delete empty medication, delete populated,
  archived medication, refusal for supplements and inconsistent links.
- Verify linked rows actually gone, unrelated records intact, audit trail
  preserved and native regimen GET/HTML counts.
- Chromium at 390px tests visible Delete, cancellation, confirmation,
  and actual native POST to isolated backend.
- Existing regimen, tablet dose and catalog tests, parse/compile gate,
  exact allowlist, detached isolated worktree, impact preflight.
- No model changes or migration, no full regression suite.

DEV only on qualified exact SHA. PROD remains at Release 727 and
requires its own separate explicit authorization.
