# Release 707 — Real signed CSRF positive lifecycles

**Baseline:** installed DEV/PROD Release 705
`4c084ade9063b3b01c2de0a4a055d2e23470b2a3`.

**Goal:** replace hypothetical signed-token probes with successful, persisted
operations and paired forged/unsigned denials. No operator flag change,
installed database access or PROD deployment is included in this candidate.

## Twelve independently specified unsafe routes

Nine from the previously unqualified Release 635 regimen workstream:

- POST `/regimen/items`
- POST `/regimen/items/{item_id}/edit`
- POST `/regimen/items/{item_id}/archive`
- POST `/regimen/schedules`
- POST `/regimen/schedules/{schedule_id}/edit`
- POST `/regimen/schedules/{schedule_id}/stop`
- POST `/regimen/entries`
- POST `/regimen/entries/{entry_id}/edit`
- POST `/regimen/entries/{entry_id}/delete`

Three previously unqualified Release 652 COA catalog routes:

- POST `/coa-test-types`
- POST `/coa-test-types/{type_id}/edit`
- POST `/coa-test-types/{type_id}/toggle`

`tests/browser/test_csrf_regimen_catalog707.py` loads only within
`/tmp/tracker-browser-qa.XXXXXXXX/data`, against the existing isolated
strict-CSRF browser server. Real Chromium obtains the signed cookie and
token from rendered HTML. For **every** route the test sends both missing
and forged tokens, requires 403, and compares SQLite state before/after
the denied requests. It then submits the *same valid business payload*
with the browser's signed token, requires an accepted 303 response and
`x-tracker-csrf-report: valid`, and verifies the affected row(s) in
private SQLite. Both HTTP and HTTPS are exercised. Created rows use
random names and reside solely in the isolated fixture.

The existing `scripts/tracker-browser-qualify.sh` full strict gate
runs the new module once; `--targeted-strict csrf-positive707` tests
only these twelve routes without an expensive complete browser pass.
`tests/test_browser_qualification511.py` explicitly registers this
strict-only module and excludes the targeted replay from its one-full
run count. `tests/test_release707_csrf_positive.py` validates that all
twelve exact route declarations were in the previously unmapped 92,
that the source has paired denial/persistence assertions, and that
the module is wired into full and targeted QA.

`scripts/tracker-csrf-positive707.sh` is a DEV-only exact SHA,
isolated-network, transient-worktree source gate and targeted real
Chromium acceptance wrapper. It requires clean installed 705 and an
active service, forbids any changed source outside the six reviewed
files, runs source and inventory tests, then executes the 707 targeted
strict workflow. No installed DEV/PROD source, data or CSRF settings
are changed.

## Qualification and closure interpretation

Until the positive browser run passes, these twelve routes are
**newly authored evidence, not certified results**. Even after targeted
acceptance, the historical 92-route ledger is intentionally not edited:
its counts reflect the older 627/705 source inventory and must be
reconciled only with auditable runtime receipts. The 80 other
outstanding routes, 155 manual reviews, six session/account paths and
global strict-CSRF activation require their own specific evidence.

A targeted Release 707 pass **never** approves global strict CSRF or
claims Issue #9 is fully resolved. The full strict browser and backend
security suites, independent session/secondary-account approval, and
safely reversible DEV and PROD rollout remain required before closeout.


## Additional 17 Workout signed positives (Release 654–668)

The same Release 707 targeted and full strict-Chromium gates now run a
second module covering seventeen new Workout write routes. It exercises
equipment creation, settings, load interpretation, routine creation and
equipment selection, routine scheduling and clearing, duplication and
item removal, quick routine start, set logging, repeat, offline sync
(including idempotent duplicate receipt), finish, historical set correction,
completed-session reuse as routine, and free quick workout start.

Each route submits the same valid business input first with missing and
forged tokens (both must deny with 403 and leave the relevant SQLite row
unchanged) and then with the actual browser session token (which must
succeed, persist the expected data and report `valid`). Both HTTP and
HTTPS are exercised SEQUENTIALLY, not in separate xdist workers, because
Tracker has one active session per scoped workout database. The test
finishes its synthetic active session.

Thus 12 + 17 = **29 distinct previously unqualified routes have newly
authored positive/negative browser acceptance tests**. They are not
counted as runtime-qualified until the guarded DEV browser run passes,
and the historical 92-route backlog is not falsified or silently
decremented. Other 63 route gaps plus 155 manual and six session/account
reviews remain subject to their separate witnesses.
