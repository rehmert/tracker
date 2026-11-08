# Release 514 candidate — manual Labs data integrity

This source-only candidate is based on Release 513:
`fad3ad8d28a21e422cbdbf13dd2fa4e56ea339be`.

## Fixed defects

1. **Non-finite manual lab measurements.** The manual report creation parser
   previously accepted `NaN`, `inf`, and `-inf`, including reference limits.
   The CSV import path and single-result edit route already rejected these
   values. The manual parser now requires finite measurements and reference
   limits before any report or attachment can be persisted.
2. **Silently omitted rows.** Form data for `analyte`, `value`, `unit`,
   `ref_low`, and `ref_high` previously used Python `zip()`, silently
   truncating to the shortest submitted array. A partially transmitted
   form could save a valid subset without warning. The parser now preserves
   all submitted rows for review and rejects inconsistent array lengths.
3. **Half-empty rows wrongly ignored.** Rows with only unit or reference
   information previously counted as blank. Only completely empty rows
   are now ignored; partly entered measurements require correction.

## Regression tests

`tests/test_lab_nonfinite_manual514.py` exercises non-finite values and
limits, valid finite results, parser parity with CSV import, incomplete
form arrays, and rejection of unsafe requests without persisting a
`LabReport` or `LabResult`. The HTTP tests use an isolated SQLite
in-memory database. No live patient records or uploads are touched.

## Release requirements

- GitHub is a source repository only; no GitHub Actions or cloud tests.
- PROD remains on Release 512/513 until the separately promoted 513 PROD
  deployment completes successfully.
- Run this source candidate via the pinned guarded **DEV LXC** release
  process at its exact commit. The DEV runner must complete browser HTTP/HTTPS
  qualification, the full backend suite, isolated recovery restore,
  and authenticated runtime smoke with `EXIT_STATUS=0`.
- Do not promote Release 514 to `main` or PROD until that qualification
  succeeds, with review of the user-facing form error messages.
- No database schema, dependency, reverse-proxy, or service changes.
