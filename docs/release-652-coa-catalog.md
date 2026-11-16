# Release 652 — Managed COA test types

## Purpose
COA test classifications are now managed at **/coa-test-types**, linked from
the COA index and document editor. A user can create reusable test types,
rename labels, change groups, deactivate or reactivate them. No deletion is
offered because historical COA records must remain interpretable.

## Data compatibility
- New additive SQLite table: `coa_test_type_catalog652`.
- The initial 24 types are seeded only during application startup, idempotently.
- Existing literal labels and Release 651 `~651~` multi-selection data are not
  rewritten, backfilled, or migrated.
- Built-in codes are stable. User-created rows have stable integer IDs.
- When needed, new selections are stored as compact `~652~` tokens in the
  existing `coa_attachments.test_type` field, still limited to 120 characters.
- An inactive type is not available for new uploads but remains selectable on
  documents that already have it.
- Legacy original-file mirrors and atomic multi-document saves are preserved.

## DEV qualification, before any production promotion
1. Back up the DEV database; create an isolated worktree at this commit.
2. Start DEV so `Base.metadata.create_all()` installs the additive catalog table.
3. Run the *scoped* gate from the isolated checkout:
   `bash scripts/tracker-coa-scoped652.sh /opt/tracker/.venv/bin/python`
4. Manually check new type creation, rename/regroup, deactivation, original
   legacy COA document, combined upload, cross-document atomic save, CSRF, and
   ordinary COA metadata editing.
5. Confirm migrations are additive and capture a qualified DEV receipt.
6. Only then use Tracker's existing guarded, SHA-pinned DEV-to-PROD process.
   Back up PROD, check the source and schema baseline, and never force-promote
   when any DEV qualification or preflight check fails.

**Status:** Source changes and regression tests are committed, but DEV tests
and guarded deployment have not been executed from this GitHub connection.
