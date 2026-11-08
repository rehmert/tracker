# Release 506 — Balance independent secondary security suites across xdist workers

## Why this release exists

Release 505 removed a redundant private worker call, improving its single
workflow duration, but paired full-suite testing found a candidate median of
72.06 s versus Release 504's 70.66 s. Release 505 was therefore **held** and
not promoted. Release 506 branches directly from deployed Release 504
(`e83e0ad1ac1729ff26e1a88a2cafdb9bb29e35f0`).

The four Release 505 benchmark reports show that the slowest individual
Release 440 private-workflow test consumes 28–31 seconds. However,
`pytest-xdist --dist=loadfile` schedules **whole files** as units. Several
6–10-second tests are grouped in one supply-use 439 file, and multiple
5–8-second tests are grouped in one reconciliation 437 file. A worker may
therefore be occupied by multiple slow tests in a single file.

This release keeps `--dist=loadfile`, all original security checks,
and authentic isolated private-worker subprocesses. It splits independent
function-scoped test cases into more file-sized scheduling units, like
the proven Release 503 integration test sharding.

## Exact test grouping

Original Release 439 supply-use module (10 original named test functions,
including the original parametrized input-rejection test) is now divided:

- `test_secondary_supply_use439.py`: authorized dose/supply use, BAC-water
  accounting, token replay, worker concurrency, forged worker input parsing
- `test_secondary_supply_use_security439.py`: invalid/overdrawn inputs,
  cross-account separation and HTML escaping, CSRF/disabled/PROD gates,
  disallowed operator requests, narrow middleware exemption

Original Release 437 reconciliation module (12 original named test
functions including the original parametrized input-rejection test) is now
divided:

- `test_secondary_reconciliation437.py`: isolated read-only stock, audited
  transitions, lifecycle restrictions, input parsing, middleware guard
- `test_secondary_reconciliation_security437.py`: account isolation and
  XSS escaping, forged input/CSRF, disabled/PROD, unauthenticated denial
- `test_secondary_reconciliation_conflicts437.py`: replay/stale token,
  changed inventory, concurrent conflict serialization

New `scripts/secondary_supply_use439_support.py` and
`scripts/secondary_reconciliation437_support.py` contain the **unmodified**
function-scoped pytest fixture and HTTP/SQLite helpers from the original
files. Tests in each shard still build fresh DEV-only credentials, private
user 2 and 3 SQLite stores, and an authenticated TestClient.

No test function bodies, parameter lists, assertions, fixture behaviors,
production application files, worker environments, process boundaries,
security gates, or deployment defaults are changed.

A new contract module, `tests/test_secondary_loadfile_sharding506.py`,
requires all original 22 function bodies to match their source fingerprints,
preserves fixture security markers and confirms full-suite collection
retains xdist loadfile with no exclusions.

## Qualification before promotion

On `tracker-dev` at Release 504, use a detached candidate worktree
pinned to Release 506 commit:

1. Validate source, `git diff --check`, compilation, untouched checkout
2. Run the five partitioned test files plus fingerprint contract, using
   `pytest -n 4 --dist=loadfile`
3. Run the **complete** 16-worker backend suite under the usual 6-GiB
   detached systemd cap; compare with Release 504's 70.66-s paired median
4. If the speedup is promising, run alternating baseline/candidate trials
   before changing DEV. Do not rely on one noisy full-suite execution.
5. Guarded DEV deployment, explicit user-confirmed success, GitHub main
   fast-forward with expected SHA, and guarded PROD deployment follow
   only if the tests and performance justify them.

The mechanism improves total suite speed **only if** these files contribute
to the critical xdist worker's queued work. Benchmark evidence, not the
test-file refactor alone, determines whether to promote Release 506.
