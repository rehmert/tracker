# Release 512 candidate — SQLite Viewer resource safety

**Candidate only.** Based on Release 511 `e377bbd9b75c1476021a57fef2fb6a74d35e6acb`.
Do not promote to `main` or PROD before separate DEV LXC qualification.

## Correctness defects

1. `sqlite_viewer_export` previously used `with sqlite3_connection`,
   which only commits/rolls back and does **not** close the connection.
   The export now uses `contextlib.closing`, including error paths.
2. The CSV exporter escaped formula prefixes only at the first character,
   unlike the other export modules. Whitespace-prefixed formulas such as
   `\t=SUM(...)` could remain dangerous in spreadsheet applications.
   Formula prefixes after leading whitespace are now escaped with an
   apostrophe, preserving the original text.
3. When `PRAGMA query_only=ON` fails during connection setup, the newly
   opened file descriptor now closes before the exception is propagated.

## Isolated regression coverage

`tests/test_sqlite_viewer_safety512.py` creates a temporary SQLite
database, checks CSV escaping, asserts connection cleanup on success
and HTTP errors, and simulates failure during read-only setup.

No real application database, account, or external service is needed.

## Acceptance rules

- **All testing runs on the DEV LXC**, never in GitHub Actions.
- Do not weaken the existing authentication, data ownership, or browser
  mutation guards.
- On DEV, run this candidate through the existing pinned guarded release
  workflow after PROD has finished its Release 511 promotion.
- Require full disposable browser qualification, backend regressions,
  backup/restore drill, authenticated runtime smoke, and explicit exit 0.
- Keep main and PROD on verified Release 511 until Release 512 has
  independently passed DEV qualification.
