# Release 584 — targeted DEV qualification preflight

**Source base:** Release 583 PROD commit `30738d9207c91e31685c299556be8023fa219e67`.

## Scope

Add a **separate, non-deploying**, pinned-commit command to identify
browser selectors, database integrity errors and backend source assertion
failures *before* the full guarded DEV release qualification.

The existing two-argument `scripts/tracker-browser-qualify.sh` and
`scripts/tracker-release.sh` full qualification path remain mandatory
and unchanged in intent. The fast mode uses a distinct
`TARGETED_STRICT_PREFLIGHT=PASSED` marker and never emits the full
`ISOLATED_STRICT_CSRF_BROWSER=PASSED` marker when used alone.

The first supported browser module is the existing Release 583
`tests/browser/test_csrf_preparations583.py`. Additional release
modules require intentional allowlist and fixture setup updates; no
arbitrary test file or helper script may run as root by argument injection.

## Targeted operator command (on DEV, once Release 584 is installed)

```bash
sudo bash /opt/tracker/scripts/tracker-targeted-preflight584.sh \
  --base <CURRENT_PROD_AND_DEV_BASE_SHA> \
  --target <NEW_RELEASE_CANDIDATE_SHA> \
  --ref release/<NEW_RELEASE_BRANCH> \
  --browser-module tests/browser/test_csrf_preparations583.py
```

The command enforces DEV-only execution and exact `main` base
match, a clean installed checkout, an exact remote release-ref SHA,
and target descendancy. It creates a disposable detached Git worktree,
compiles source, validates both shell entry points, and runs only
changed backend tests plus the fixed browser/583 contract tests.
The backend test database is isolated under `/tmp`. It then calls
the modified browser qualification with `--targeted-strict`, which
starts disposable 127.0.0.1 HTTP/HTTPS servers, enforces strict CSRF
**only** there, creates synthetic inventory and supplies, runs the
complete two-transport Release 583 browser lifecycle, validates the
private evidence receipts, and independently reconciles persisted stock.

The private root-owned log is retained at
`/tmp/tracker-preflight-584.XXXXXXXX/preflight.log` and the exact
path and final return code are printed. No remote host deployment,
installed database mutation, systemd restart, GitHub Actions, auth-file
copy, or DEV-to-PROD promotion occurs.

## Required full release workflow remains

After preflight success, run the normal
`sudo bash /opt/tracker/scripts/tracker-release.sh --instance DEV
--base ... --target ... --ref ...`.
That guarded runner **still executes all browser suites and the entire
backend regression suite, recovery archive, restore test, and installed
runtime smoke**. Then complete DEV visual approval, non-deploying
`tracker_promote568.py` preflight, and operator-authorized signed
DEV-controlled PROD promotion.

## Future bundled strict-CSRF work (585–586)

After 584 is promoted, plan **one combined release**, rather than
two separate deployments:

- Extend the targeted strict browser allowlist to its new tests.
- Exercise remaining high-risk native/multipart, inventory, and
  secondary-account flows under isolated strict HTTP/HTTPS.
- Keep missing/untested callsites explicitly unqualified.
- Deliver a readiness and rollback decision; never automatically
  enable `TRACKER_CSRF_ENFORCE=1` on installed DEV or PROD.

Issue #9 remains open until all requirements are actually satisfied.
