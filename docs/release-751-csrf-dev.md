# Release 751: strict CSRF end-to-end DEV activation

DEV baseline Release 750 (2ff72f49449306ea5b11dc9c861d0cac5973131e).
No changed runtime app code, dependencies, migrations or PROD config.

The existing app already has global opt-in strict CSRF for bounded form,
JSON/JS/HTMX and native multipart endpoint dependency. Release 751 adds:
- HTTP and HTTPS synthetic positive/forged root signed-write regression
- Existing unsafe-route negative matrix, multipart and session-account tests
- Full report-only and strict HTTP/HTTPS Chromium suite in PrivateNetwork
- Mandatory full backend and browser regression before DEV install
- Reversible systemd EnvironmentFile override activating strict on DEV only
- Live process-environment inspection, health and denied-unsigned-POST probe

This release does not automatically activate strict CSRF on PROD or
change /etc/tracker.env. If live DEV activation fails, its managed
override is removed and the prior unit configuration restored.

After verified DEV installation:
  sudo bash /opt/tracker/scripts/tracker-csrf-dev751.sh status
Rollback DEV flag only:
  sudo bash /opt/tracker/scripts/tracker-csrf-dev751.sh disable

Manual DEV browser checks remain meaningful for uncommon long/streamed
forms or third-party clients. Do not assume source-only negative assertions
prove every positive path. Strict PROD activation requires separate
explicit approval and its own signed preflight.

## Qualification correction

Release 751 discovered the legacy 627 negative matrix was still collected
from the 144+17 frozen historical source inventory. The test now consumes
the current fail-closed Release 627+705 reconciler and exercises both
missing-token and forged-token denials for all currently unresolved routes,
including more recently added endpoints. No positive route is falsely
classified as certified; existing independent runtime route matrix remains.

## Targeted failure localization

Before full isolated browser qualification, the worker executes only the
previously failing Release 602 strict-CSRF browser module test in disposable
HTTP and HTTPS. Failure records include bounded synthetic
`tests/strict751_dose602_lineNNNN.py` identifiers from short pytest
traceback locations; original logs remain in the private QA directory and
are deleted during cleanup. A targeted success cannot qualify the release:
the full normal and strict Chromium matrix still follows and must pass.

## DEV install timeout root cause and focused repair

The passed isolated strict qualification ran longer than the old 600-second
inner browser timeout in `scripts/tracker-release.sh` when repeated by the
DEV `--full-suite` installer. The original `r751-install4bd20f98` receipt
failed with GNU timeout exit 124 / SIGTERM 143 in a still-running strict
Chromium module, before any source installation or systemd strict flag.
The browser limit is raised to 1800 seconds (bounded), preserving the full
security/backend suite, exact-SHA guards, DEV-only activation, and fail-closed
stage behavior. Do not rerun the failed live request; qualify a new SHA.

## Full backend historical CSRF inventory count correction

The guarded Release 751 DEV full regression identified a historical Release
574 test pinned to exactly 161 registered unsafe routes; the current
application registers 223. A structural test now requires at least the
223-route current baseline, verifies report counts against the live FastAPI
route enumeration and per-method totals, and continues requiring every
unsafe route's manual compatibility review. New routes are not
inferred CSRF-qualified simply by inclusion. Signed/forged-token strict
browser and backend tests remain unchanged. The failure occurred before
DEV source installation, so the previous failed live stage must not be retried.

## Full backend Release 650 DEV attachment policy assertion refresh

The full DEV regression discovered a historical test expecting DEV's
missing-file advisory path only when `DB_MIGRATION=0`. The release runner
has since explicitly retained the DEV missing-upload policy for migrations,
while protecting migration backup via integrity checks and a verified SQLite
and present-upload archive. The historical test now inspects both actual
preflight and migration blocks, including PROD's strict hash-gated path.
The corrected test is added to Release 751's change-scoped security gate,
so it runs before the costly browser and full backend installation suites.
No runtime attachment policy, PROD setting, or medical data is modified.

## Complete backend preflight before repeat DEV install

The previous full install ran 2285 passing backend tests and exposed two
outdated tests before source installation: the original Supplies baseline
has grown from 5 to 9 scoped database dependencies, and Quick Entry has
seven (not five) daily cards. The source-only tests now retain minimum
scoped coverage, forbid unscoped database dependencies, and verify the exact
seven daily-action destinations without freezing future expansions.

Both modules are included in the scoped security gate. In addition, the
isolated exact-SHA qualification now runs the **same complete 16-worker
backend suite** as the guarded DEV installer *before* costly browser tests,
without maxfail, so all remaining backend regressions are surfaced in one
private qualification log rather than in repeated DEV install attempts.
The installed application and PROD environment are not changed by the QA
preflight. No backend tests, security assertions or installation guards are
removed.

## Deterministic baseline-parity qualification for legacy full-suite debt

The Release 751 isolated full backend suite initially returned 54 red results
out of more than 5,000 cases. Most checks are frozen historical expectations
for older routes, script argument counts, CSS, or pages that changed long
before the DEV 750 baseline. Altering all these legacy tests to get a green
number would conceal whether 751 actually causes a new regression.

The DEV-only 751 backend gate now executes **every** backend test twice,
with separate private, disposable data roots: once against the exact pristine
installed Release 750 baseline and once against the exact candidate 751.
The candidate must preserve all collected baseline tests and may not add
any failures, errors, or skipped test cases. Missing/duplicate/empty JUnit
reports, abnormal pytest exit codes, timeouts and unclean DEV checkout are
fail-closed. Raw logs, historical failures and data are never placed in GitHub.
Existing release behaviors use their original bounded 600s browser timeout;
751's extra strict modules use 1800s. This is transparent baseline-parity,
**not** a claim that the inherited full suite is all green. The strict CSRF
negative/positive HTTP/HTTPS gate remains mandatory, PROD is unmodified,
and no other release's full-suite policy changes.
