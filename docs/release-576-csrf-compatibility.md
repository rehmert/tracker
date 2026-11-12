# Release 576 — strict CSRF JS triage and executable preparation correction

Baseline: Release 575 commit `db0063345b3d6380d51cae14eadb96d704605fb2`.
This release is a **tooling/test-only candidate**, not a CSRF policy rollout.
Issue #9 remains open. Installed DEV and PROD must remain report-only.

## Bundle

1. `scripts/tracker_csrf_js_triage576.py` preserves all 46 Release
   575 callsite records and separates literal evidence **on the callsite
   line** from the untrusted nearby method hints. It records literal
   paths when apparent on that same line, but never claims that a
   method, endpoint or CSRF token was executed. All 46 remain pending
   runtime verification. The output is source-only and contains no
   client request payloads or secrets.
2. `tests/test_release576_csrf_js_triage.py` tests full inventory
   preservation, path-traversal rejection, source-hint non-attribution,
   dynamic and explicit-method examples, and private JSON output.
3. The existing isolated browser fixture now includes two disposable
   `PreparationEvent` rows. Neither is created on an installed
   database; fixture creation runs only within
   `/tmp/tracker-browser-qa.*/data`.
4. `tests/browser/test_strict_csrf521.py` exercises the implicit
   `preparation_edit.html` native POST action using real Chromium on
   local HTTP and host-rewriting HTTPS. Each case first proves an
   unsigned forged write is denied without changing the note, then
   submits an actual signed correction and verifies the redirect and
   updated note. This test performs no live user-data mutation.

## Evidence and limitations

The resulting source-only report is a prioritized **review queue**, not
a route-by-route clearance certificate. Nearby literal POST is not
proof that the callsite makes a POST. The 19/27 Release 575 triage
partition remains a historical heuristic; Release 576 provides more
specific, still conservative hints. Full JS write classification,
secondary-account strict browser flows, unusual multipart/large-body
cases, proxy-origin edges, and a route-by-route executable coverage
matrix remain open under Issue #9.

## Prequalification / DEV gate

The guarded runner must execute compile checks, backend regressions,
strict disposable browser tests with both schemes, recovery verification
and dependency drift audit. Focused tests before the release gate:

```bash
cd /opt/tracker
.venv/bin/python -m pytest -q tests/test_release576_csrf_js_triage.py tests/test_release575_csrf_js_review.py
```

This standalone command is for a checkout of the candidate source,
**not** a request to change the installed DEV checkout before the
guarded release. The guarded worker runs its own isolated checkout.

Generate a private review report on a qualified candidate, without
altering the installed strict setting:

```bash
cd /opt/tracker
DIR=$(mktemp -d /tmp/tracker-csrf576.XXXXXXXX)
.venv/bin/python scripts/tracker_csrf_js_triage576.py --json "$DIR/review.json"
```

No live DEV strict-CSRF rehearsal is authorized by this change.
That will require a separately approved, reversible plan with explicit
rollback and identity checks. PROD enforcement requires independent
approval after DEV rehearsal evidence.

## Release procedure

Deploy through `scripts/tracker-release.sh` from `tracker-dev`
using exact pinned base and candidate SHAs. Review
`TRACKER RELEASE DEPLOYMENT SUCCESS`, `EXIT_STATUS=0`, the strict
browser results, dependency audit and recovery verification before
any signed PROD promotion through `scripts/tracker_promote568.py`.
Changes are confined to `scripts/`, `tests/`, and `docs/`; no
application restart is expected from this bundle.
