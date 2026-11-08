# Release 501 — Food Journal / Labs Quality Cycle

## Scope

- **Food Journal:** Favorites and Recent Foods show a warning when multiple
  saved products share the same normalized name, barcode, and serving size.
  The warning identifies the saved record ID. Nutrition data, meal history,
  and existing save/reuse actions are never altered.
- **Labs:** analyte-history CSVs include original results, conversions,
  printed reference intervals, report IDs, result IDs, and result notes.
  Filenames use a bounded ASCII slug rather than untrusted analyte text.
  Existing per-report exports and CSV import formats are unchanged.
- **Native form compatibility:** the global `Referrer-Policy` becomes
  `same-origin`, which avoids `Origin: null` on legitimate native POSTs
  while withholding all referrer information from cross-origin requests.
  The existing Origin guard still rejects `null`, foreign, and cross-site
  requests. Explicit stricter endpoint policies remain intact.
- **Browser quality:** disposable, loopback-only HTTPS test proxy checks
  native multipart Labs create/upload, edit, and delete, plus a negative
  cross-site write. Tests never touch the installed DEV or PROD database.
- **Release diagnostics:** isolated browser qualification runs before the
  long backend suite on DEV, retains its own pytest failure log, and prints
  the failure summary after cleaning up candidate processes. PROD retains
  the full backend and backup/restore gates.

## Release invariants

1. No schema migration, new runtime dependency, authentication change,
   CSRF enforcement change, or production proxy configuration change.
2. Candidate application is launched in a detached Git worktree with a
   separate temporary SQLite data directory.
3. HTTPS certificate/key are generated only for the isolated local test;
   the key is removed when the test proxy stops.
4. Original food nutrients and saved variants remain independent records.
5. CSV fields that originate from editable text retain formula escaping.
6. Never promote to GitHub main before a successful guarded DEV deployment.

## Qualification order

1. Check pinned branch SHA and clean installed Release 500 baseline.
2. Run source syntax, release-contract tests, and targeted Food/Labs tests.
3. Run `scripts/tracker-browser-qualify.sh` against a disposable worktree.
4. Review native HTTPS submissions, upload, deletion, and cross-site denial.
5. Run guarded DEV deploy (which repeats browser **before** full backend tests),
   including archive/restore and runtime smoke checks.
6. Promote exact verified DEV commit to main with a fast-forward lease.
7. Run guarded PROD deploy and verify service health.

A browser failure means this release is not deployable; investigate
`BROWSER_TEST_LOG` before changing application security behavior.
