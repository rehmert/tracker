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
3. Run the **Release 652-only** gate from the isolated checkout:
   `bash scripts/tracker-release-scoped652.sh /opt/tracker/.venv/bin/python`
4. Manually check new type creation, rename/regroup, deactivation, original
   legacy COA document, combined upload, cross-document atomic save, CSRF, and
   ordinary COA metadata editing.
5. The DEV-only migration backup records the known unsynchronized missing
   `uploads/coa/b94356f52d964400b481e6c743484367.png` explicitly. The
   exact SQLite snapshot and all existing attachments are checksum verified
   through a restore rehearsal. Any other missing file, invalid path, or
   present-file hash mismatch blocks deployment. This exception is NEVER used
   on PROD, which retains the standard fully complete backup gate.
6. Confirm migrations are additive and capture a truthful release-scoped DEV receipt.
7. Only then use Tracker's existing guarded, SHA-pinned DEV-to-PROD process.
   Back up PROD, check the source and schema baseline, and never force-promote
   when any DEV qualification or preflight check fails.

**Status:** Source changes and regression tests are committed, but DEV tests
and guarded deployment have not been executed from this GitHub connection.

## Testing policy (effective Release 652)
Run only a release-specific test script and directly affected compatibility
checks by default. The full backend and browser suites are **opt-in with
`--full-suite` only**; do not trigger them automatically at five-release
milestones. For security-sensitive core changes, fail closed and require an
explicit full-suite authorization rather than running it without consent.
