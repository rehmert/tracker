# Release 583 — signed vial preparation / supply accounting

**Base:** Release 582 PROD commit `64778c1631a4a1778a221ac17e782c8638abd16f`.

## Isolation and security posture

All new browser writes execute **only** against the existing disposable
127.0.0.1 HTTP/HTTPS candidate in `TRACKER_CSRF_ENFORCE=1` mode.
The new synthetic supply fixture refuses to run outside its
`/tmp/tracker-browser-qa.XXXXXXXX/data` directory with all required
isolation flags. No installed DEV or PROD database is touched by these
tests, and no installed application runtime routes or security mode
are changed. Global installed strict CSRF stays **report-only**.
Issue #9 stays open.

## Browser write coverage

Two signed lifecycle cases run, one per transport, on preexisting synthetic
vials #1 and #2. Each has four real native-form POSTs with CSRF-valid
responses and corresponding unsigned-request HTTP 403 rejection checks:

1. Reconstitute 2 mL, choose the synthetic BAC water inventory and
   record one needle. Verify the one-time reconstitution form disappears.
2. Record a filtering event consuming one swab and identify its saved
   event dynamically through its unique QA note.
3. Edit that event through its native correction form. Replace the swab
   with two needles, preserving the correction notes.
4. Delete the filtering preparation through the visible form and confirm
   its history disappears and its edit endpoint returns HTTP 404.

The earlier Release 579–582 strict Chromium modules remain mandatory.

## Independent inventory reconciliation

The runner inserts three synthetic stocks **after** prior strict suites
finish (10 mL BAC water, 10 needles, 10 swabs).
After both browser cases complete, a separate Python database verifier
checks exact persisted inventory:

| Supply | Initial | Final | Interpretation |
|---|---:|---:|---|
| BAC water (mL) | 10 | 6 | Two reconstitutions, 2 mL each |
| Needles (count) | 10 | 8 | One reconstitution needle per vial; corrections restored |
| Swabs (count) | 10 | 10 | Filtering consumption reversed by correction and deletion |

It also checks both vial volumes, one reconstitution event per vial,
the exact preparation linkage, and the BAC-water usage records.
Any discrepancy fails the isolated browser gate.

The private runtime validator requires exactly two 0600 JSON witnesses,
and rejects extra, missing, tampered or insecure receipts. No credentials,
CSRF values, user records or actual identifiers appear in receipts.

Expected guarded DEV evidence markers (not yet executed):

```text
CSRF_583_SYNTHETIC_SUPPLIES_SEEDED=YES
CSRF_583_PREPARATION_EVIDENCE=VERIFIED
CSRF_583_SIGNED_WRITES=8
CSRF_583_FORGERY_REJECTIONS=8
CSRF_583_SCOPE=VIAL_PREPARATION_HTTP_HTTPS_ONLY
CSRF_583_SUPPLY_ACCOUNTING=VERIFIED
```

## Remaining compatibility work

A signed vial deletion lifecycle, wider bulk inventory mutations,
and multi-account isolation under global strict-CSRF conditions are not
proven by this release. The source-only JS ledger must not be presented
as live runtime clearance. Keep global strict-CSRF report-only on
installed DEV and PROD until separately authorized.

Use exact-commit guarded DEV qualification, DEV visual review,
non-deploying promotion preflight and operator-authorized
DEV-controlled PROD promotion. Do not deploy from GitHub Actions.
