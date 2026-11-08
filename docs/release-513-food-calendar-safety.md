# Release 513 candidate: Food Journal date bounds and calendar export safety

This source-only change is based on **Release 512**
`5c95ffc497301208559efc0ff09200b5c49e6823`.

## Issues fixed

### 1. Food Journal and weekly view overflow near year 0001

Release 511 guarded only the first and last representable `date` values
when viewing the Food Journal. Both its seven-day dashboard summary and
its weekly nutrient export subtract six days from the selected date.
Dates `0001-01-02` through `0001-01-06` therefore remained able to
cause an unhandled `OverflowError` (HTTP 500).

One shared date-range validator now guarantees that the selected day has
six predecessors and one successor. GET and POST routes, quick logging,
weekly summaries, and weekly CSV use this bound consistently.
It rejects unsupported dates with HTTP 422. Normal journal dates and
existing stored records are unchanged. Date validation on the dashboard
occurs before schema initialization.

### 2. Malformed iCalendar from protocol names containing carriage returns

The `/calendar/export.ics` TEXT encoder previously escaped LF but not
bare CR or CRLF. Imported or user-entered protocol/compound text could
generate illegal ICS content lines, including injected property names.

The encoder now normalizes CRLF and bare CR to LF *before* escaping TEXT.
It continues escaping backslash, comma, and semicolon and preserving
the existing 75-octet UTF-8 line folding.

## Isolated tests

`tests/test_food_calendar_edges513.py` includes temporary in-memory
SQLite fixtures, date range tests, negative Food Journal GET/POST tests,
a positive earliest supported weekly CSV, TEXT escaping checks, and
synthetic ICS injection attempts. No live data is needed.

## Acceptance and deployment

- Keep GitHub strictly for version control. **No GitHub Actions or cloud
  test execution.**
- Qualify this pinned candidate on the **DEV LXC** through the existing
  guarded `scripts/tracker-release.sh` workflow, including disposable
  HTTP/HTTPS browser tests, full backend regression tests, verified
  recovery backup and isolated restore, and authenticated runtime smoke.
- Do not promote to `main` or PROD until DEV returns the verified target
  SHA with `EXIT_STATUS=0`.
- These fixes have no database schema or dependency changes.
