# Release 519 candidate — bounded Health Timeline SQL pagination

Base: PROD-qualified Release 518 `9c9c06845ad101bba681b56120244d1531861708`.

## Why
The unsearched Health Timeline previously loaded every matching vital, dose,
lab, and active protocol row into ORM objects, formatted and sorted the entire
history in Python, and only then sliced the selected 25/50/100-entry page.
On large histories this causes unnecessary memory and relationship reads.

## Implementation
- A new read-only SQL UNION index represents each historical event as a small
  source/id/timestamp/type/link tuple. SQL GROUP BY calculates type counts.
- SQL ORDER BY/OFFSET/LIMIT selects the requested page; only its models and
  related rows are loaded into Python, in bounded batches.
- Date presets, inclusive custom ranges, "All history", event-type counts,
  active-only protocol dates, waste/dose distinctions, tie order, and page
  clamping are preserved.
- **Free-text search** retains the existing full-history renderer to preserve
  exact casefold matching and full text across formatted fields.
- **CSV export** still uses the original full-history source so no matching
  rows are omitted by page limits.

## Test evidence required on DEV
`tests/test_release519_timeline_pagination.py` constructs a standalone
in-memory database containing hundreds of synthetic mixed events. It compares
every SQL page with the original Python reference across all event types,
several page sizes, negative/oversized page numbers, inclusive and one-sided
date ranges, protocol ties, and the unbounded All preset. It also tests
bounded SELECT counts and real HTTP/CSV/search route compatibility.

The tests have been committed but **not yet executed on the DEV LXC**.
All data and SQL changes are read-only; no database schema, migration,
dependency, installed service, or user permissions change.

## Qualification
GitHub is repository/source control only. No GitHub Actions/cloud tests.

Use the exact commit on `improvement/release-519-timeline-sql-pagination`
in the existing pinned guarded DEV LXC release runner and require:
1. compilation and full backend regression suite;
2. disposable browser/HTTPS qualification and report rendering;
3. backup/recovery drill with isolation from live data;
4. runtime health and sidebar checks, plus `EXIT_STATUS=0`.

Check that searching and downloading all matching CSV rows still work on DEV.
Do not promote to main/PROD until this exact SHA is DEV-qualified.

## Follow-up separately scoped
- Global CSRF strict enforcement still needs a legacy multipart/browser review
  and a separate compatibility gate (issue #9); no enforcement flag changed.
- COA ORM declaration cleanup touches `app/models.py` and remains explicitly
  blocked by the existing guarded release script until separately reviewed.
- Dependency pinning still requires actual LXC package snapshots (issue #10).
