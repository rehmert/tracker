# Release 708 — 19 remaining Workout positive CSRF lifecycles

**Baseline:** deployed Release 705
`4c084ade9063b3b01c2de0a4a055d2e23470b2a3`.

**Prerequisite:** successful DEV-only Release 707 exact-source targeted run
`537e938151ee12624998dbf93be8cd6249692547` with
`RELEASE_707_VALIDATED_SIGNED_ROUTE_COUNT=29` and exit 0.

Release 708 builds on Release 707, preserving its passing 9 regimen,
3 COA catalog and 17 Workout positive-browser tests.

## The remaining 19 post-653 Workout unsafe routes

`tests/browser/test_csrf_remaining_workout708.py` covers every Workout
route not in the passing Release 707 Workout suite:

- Historical backfill, historical CSV import
- Native start, finish, and finish-and-review
- Routine start, group add/remove and item move/substitution
- Program rest, per-item goal, JSON plan import, CSV plan import
- Native set logging, repeat, active set editing/deletion
- Undo of the latest audited historical set correction

Each real Chromium case renders the Tracker form token and cookie.
For each route it sends the same business payload **without a CSRF
token and with a forged token**. Both must return HTTP 403 and leave
relevant persisted SQLite values unchanged. Next, a valid browser
session token must be reported as valid and the operation must succeed,
with a **specific state invariant** for the modified row(s). Both
real HTTP and HTTPS requests are exercised sequentially in one
test to preserve Tracker's singleton active workout constraint.
The specimen form and DB are under the existing disposable
`/tmp/tracker-browser-qa.XXXXXXXX/data` root.

All 19 exact paths are statically checked against the Release 627/705
unqualified list, and together with the 17 Release 707 Workout paths
must equal all 36 later-version Workout declarations.

## Qualification

`scripts/tracker-browser-qualify.sh` registers the new module once
in its full strict browser gate, plus a targeted
`--targeted-strict csrf-positive708` mode. The existing
`tests/test_browser_qualification511.py` strict-only allowlist is
updated to prevent accidental report-only execution and avoid counting
targeted replay as a duplicate full-run.

`scripts/tracker-csrf-positive708.sh` is invoked from a pre-fetched,
exact GitHub commit via detached `systemd-run -p PrivateNetwork=yes`.
It uses a temporary detached source worktree on `tracker-dev`,
requires clean installed 705, verifies **all 11 changed paths** against
the fixed allowlist, runs targeted source and browser qualification
tests, executes the real 19-route HTTP/HTTPS test and removes all
disposable data. No DEV/PROD deployment, installed database changes,
global strict CSRF switch or dependency modifications.

**A successful 708 targeted test will add 19 positive-route runtime
witnesses, yielding 48 newly exercised routes across the two approved
707 and 708 source commits.** This is *not* global CSRF clearance.
The original conservative `CSRF_705_UNMAPPED_POSITIVE=92` source ledger
will remain unchanged until auditable source+runtime receipt reconciliation
is implemented. Other historical and non-Workout routes, 155 manual
reviews, six session/account paths and a full strict browser gate still
require their own separate approval. Issue #9 stays open.
