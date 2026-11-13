# Release 595 — Food lifecycle and vendor-sheet CSRF qualification

Base: Release 594 `471b1df7b1b31bed83894c6e2e558d1fd3a72d01`.

This candidate extends the existing disposable strict-CSRF Chromium gate with
**10 source-witness routes** over both HTTP and HTTPS.

- Food: individual entry edits, copy-on-write nutrition corrections, saved
  food favorite toggling, quick log, and meal-template save/rename/log/delete.
- Vendor prices: reviewable tab-separated sheet save and sheet deletion.

Each route gets a native same-origin signed browser POST and a separate
unsigned 403 rejection assertion. Playwright waits for the original POST
response rather than the final redirected HTML; response reports and
originating request CSRF headers must be valid. SQLite reads are restricted
to the guarded `/tmp/tracker-browser-qa.*` database to verify persisted
values, copy-on-write isolation of the original product, historical logged
food retention after template deletion, and vendor-sheet cascade cleanup.

All 10 routes are explicitly mapped in the readiness source and the full
browser gate source planner, with an additional fail-closed browser test
function check. The prior 4-worker isolated Chromium limit stays in place.
The 16-worker backend regression runner is unchanged. There are no app
runtime, database migration, session account, or global CSRF policy changes.

Expected source-only inventory under the unchanged 144-route ledger:
**70 candidates, 74 without source witnesses** (57 routes in the explicit
witness manifest). This report **does not** represent runtime verification
or authorize global strict-CSRF enforcement. Multipart vendor uploads and
CSV import previews/saves still require separate workflows and stay in
the unqualified queue.

The full guarded DEV qualification must pass before this candidate is
considered executable evidence. PROD requires the standard promotion dry
run, explicit authorized execution, and exact-commit verification.
