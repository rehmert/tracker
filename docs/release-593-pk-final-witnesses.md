# Release 593 — Remaining PK full-browser CSRF source witnesses

Base: Release 592 `4f26cda675e8549c54e31a7fbbb63fa257220259`.

This candidate **adds no application feature changes**. It extends the
mandatory disposable strict Chromium HTTP/HTTPS test module
`tests/browser/test_strict_csrf521.py` with three full workflows:

1. **Guarded scenario changes and history**: revision-header-checked
   bulk dose creation, revision-checked individual dose edit, audit preview,
   and revision restoration. Each signed POST is preceded by tokenless
   rejection and followed by persisted scenario-state assertions.
2. **What-if modeling**: signed single-schedule preview, normalized
   multi-preview, and saving a what-if scenario; previews are never
   represented as mutations. Saved scenario is verified via GET and removed
   from the disposable QA database.
3. **Saved-protocol workbench and experiment library**: creates an
   explicit test-only Protocol/ProtocolItem in the browser server's guarded
   `/tmp/tracker-browser-qa.*` SQLite database. Exercises signed, forged-
   denied stateless workbench POST, library save, library revision PUT,
   comparison POST, and deletion. The experiment list and historical
   revisions must reflect the writes. Only disposable QA data and files
   are accessed.

These tests give positive signed HTTP/HTTPS coverage to the final **11 PK
unsafe-route declarations**. The 590 gap planner now maps all 31 PK source
routes to mandatory strict Chromium witnesses, and guards the actual browser
test function names. The original 591 negative matrix still includes all
31. Existing legacy 590/591/592 source contracts are reconciled.

Assuming the unchanged 144-route ledger, report-only inventory should
become **50 source candidates and 94 unqualified routes**, with zero
remaining *PK source-only* gaps. This is **NOT** proof of runtime execution:
the complete DEV qualification must pass before citing these witnesses
as executed. It is also **NOT** global CSRF policy clearance; the
application remains report-only and the manual-review queue, other URL
workstreams, account isolation, and rollout policy remain outstanding.

For this candidate use one disposable source-contract preflight followed by
one full guarded DEV deployment. No browser runner, dependency, installed
config, migration, or application files change, and no standalone targeted
preflight is necessary. PROD promotion must separately pass the unchanged
guarded dry run and authorized execute path.
