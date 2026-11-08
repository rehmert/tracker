# Release 505 — Remove redundant authenticated integration-test GETs

## Baseline and constraint

Release 504's 16-worker full suite qualified at **2,601 passed, 1 skipped in
65.75 seconds**. Its full private workflow made **25 independent private-worker
subprocess calls**, taking 25.978 seconds, and the HTTP requests took 27.453
seconds. A private worker is intentionally short-lived and must independently
validate its database and account isolation. This release **does not** bypass
that architecture or change production code.

Code review identified six pairs of duplicated HTTP GETs in existing
integration tests where no account identity, flag, record or CSRF state changes
between the first and second request. Each GET launched a real private-worker
subprocess.

## Narrow changes

- Full private workflow: reuse the already verified vial-correction detail
  page for its existing form POST; retain the real GET, snapshot assertion,
  real CSRF/submission token and real POST, audit and cross-account assertions.
- Dose creation and reconstitution: reuse the existing authenticated GET
  response already checked for correct private-vial HTML, then submit the
  exact form tokens in a real HTTP POST. Form helpers still use fresh GETs
  in every other test.
- Supply intake HTML escaping: inspect escaped and non-escaped strings in
  the *same* response instead of fetching the identical page twice.
- Disabled supply intake and disabled supply use: inspect HTTP status and
  the missing write form/link from one real disabled-state GET, retaining
  the disabled POST's HTTP 404 assertion.

Form helpers accept optional previous responses only from the exact
`GET` route without query parameters and with HTTP 200 status. They never
reuse responses across users or after data mutations. The explicit
`tests/test_secondary_form_reuse505.py` exercises exact route binding,
POST token propagation, mismatch rejection, and test security assertions.

No production files, migrations, runtime options, worker subprocesses,
session mechanisms, CSRF algorithms or security checks are changed.

## Qualification

1. Verify a clean Release 504 DEV installation and exact Release 505 SHA.
2. Run `git diff --check` and Python compilation on a disposable git
   worktree; do not touch the installed checkout.
3. Run `tests/test_secondary_form_reuse505.py` and all modified
   integration modules in a focused two-worker pytest run, with actual
   private SQLite data, worker subprocesses, and credential hashing.
4. Run the unchanged full private workflow with the Release 504 profiler,
   confirming 24 (not 25) worker invocations and no failed assertions.
5. Run the complete non-browser backend suite at 16 workers, with 6 GiB
   memory limit. Do not suppress, delete, skip, or alter other tests.
6. Only if the real full suite and guarded DEV deployment pass, promote
   the exact qualified commit to main and deploy with the guarded
   serial-production release script.

The projected improvement is modest and should be *measured* rather than
promised: roughly six avoided child processes across the suite, with one
avoided invocation on the full private-workflow test's critical path.
