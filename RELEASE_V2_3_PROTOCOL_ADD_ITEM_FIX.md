# Tracker v2.3 — Protocol Add Compound Fix

- Replaced the protocol editor's HTMX-dependent Add item button with a standalone GET request and DOM insertion. This permits adding a row even when another row is incomplete, and reports request failures in the editor instead of silently failing.
- The new row is initialized for HTMX interactions and focused for keyboard entry.
- Disabled browser form validation on the what-if editor form; the server continues to parse and validate submitted values, so incomplete rows are not saved.
- Added an end-to-end regression test for creating a compound, fetching a new protocol row, saving it, and viewing it.
- All 128 tests passed with `PYTHONPATH=. pytest -q`.
- No database migration. Existing protocols are preserved.
