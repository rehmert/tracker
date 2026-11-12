# Release 576 — strict-CSRF JS classification, preparation correction, and session negatives

**Pinned base:** Release 575, `db0063345b3d6380d51cae14eadb96d704605fb2`.
**Issue:** [#9](https://github.com/rehmert/tracker/issues/9).
**Candidate branch:** `release/576-csrf-js-route-acceptance`.

This release is **source/tests/tooling only**. It does not change `app/`,
database schema, dependencies, installed service configuration, authentication
settings, or `TRACKER_CSRF_ENFORCE`. The guarded runner should take its
no-service-restart path, preserving the existing DEV/PROD application behavior.

## Added review and acceptance coverage

1. `scripts/tracker_csrf_review576.py` reuses the exact Release 575 scanner
   inventory and individually extracts each source `fetch(...)` or
   `htmx.ajax(...)` expression. It distinguishes explicitly unsafe method
   literals, explicit GET, implicit GET with textual URL expressions,
   dynamic methods, unknown `Request` inputs/options and unparsable
   expressions. **None of these source categories proves runtime security.**
   It produces the complete source-level callsite queue and per-static-route
   test-definition review rows, without accessing the live app, credentials,
   users, or network. A `--json` file is allowed only in a fresh private
   `/tmp/tracker-csrf576.*/` directory and is created mode 0600.
2. `tests/test_release576_csrf_js_review.py` covers the source parser,
   nearby-unrelated-literal false positives, dynamic requests, htmx,
   nested expressions, path confinement, private output, the 46 prior
   callsites and the static write-route evidence queue.
3. `tests/browser/test_strict_csrf576.py` adds **actual Chromium requests**
   on HTTP and the host-rewriting HTTPS proxy. The browser runner creates
   two dedicated disposable vials. Each undergoes a signed reconstitution,
   a rendered implicit-action `preparation_edit.html` form, a rejected
   forged correction and a successful genuine correction.
4. The same strict browser suite tests JS POST/FormData CSRF headers for
   `/vials/bulk/validate-selection` and
   `/vials/bulk/delete-preview`, rejects missing and forged tokens, and
   rejects a cross-site origin even with an otherwise valid signed token.
   **No bulk deletion takes place.** A separate >64 KiB URL-encoded
   form-body test proves the unsigned request is denied while a
   signed-header read-only validation is accepted.
5. Extended `tests/test_release521_strict_auth_compatibility.py` verifies
   no-token and forged-token administrator password changes, secondary
   password changes and logout, and cross-site secondary session revocation
   under the existing strict-mode disposable authentication setup.

All browser writes operate against the existing, isolated
`/tmp/tracker-browser-qa.*/data` test database, never the installed
DEV/PROD databases. Browser tests fail collection if their isolation flags,
local-only HTTP/HTTPS ports, or temporary data directory are missing.

## Limits and rollout gate

The source scanner is conservative and **not** a JavaScript interpreter.
Read-only business logic implemented as POST still requires CSRF protection.
The static route queue is not identical to the FastAPI 0.162 effective
runtime inventory (144 unsafe registrations in Release 575). Each row
identifies a test definition where known but deliberately marks it
**not executed by the report**.

Do not confuse successful Release 576 DEV qualification with approval for
global strict enforcement. Further work is required on less-exercised
write routes, conditional secondary configurations, additional uploads,
full runtime route-to-browser coverage and a reversible live DEV rehearsal.
Issue #9 remains open. `TRACKER_CSRF_ENFORCE` stays report-only on
installed DEV and PROD. A future live DEV-only policy rehearsal requires
explicit operator approval, a rollback procedure and verified health.
PROD requires a separate, later approval.

## Review output (optional, after successful DEV qualification)

On `tracker-dev`, in a private root shell:

```bash
set -Eeuo pipefail
cd /opt/tracker
DIR=$(mktemp -d /tmp/tracker-csrf576.XXXXXXXX)
trap 'rm -rf -- "$DIR"' EXIT
.venv/bin/python scripts/tracker_csrf_review576.py --json "$DIR/review.json"
install -m 600 "$DIR/review.json" /etc/tracker-release/release-576-csrf-review.json
```

The report remains source evidence; it cannot certify live enforcement.

## Qualification

1. Verify the exact base SHA on `tracker-dev`, clean Git main, branch SHA
   and ancestry. Use a disposable Git worktree and isolated `TRACKER_DATA_DIR`
   for focused parser and session-security tests.
2. Execute the single guarded `scripts/tracker-release.sh` DEV operation
   against the pinned candidate SHA; it compiles Python, checks Jinja,
   runs the isolated regular + strict Chromium suites, full backend suite,
   dependency baseline and restore checks through the established gates.
   **Never mark this release qualified without the actual success log.**
3. After DEV qualification and operator review, use the established signed
   DEV-controlled promotion preflight (`scripts/tracker_promote568.py`)
   before any separately authorized PROD action. No GitHub Actions deployment.

## Completion evidence required

- Focused tests passed before guarded DEV invocation.
- Browser runner: `DISPOSABLE_PREPARATION_FIXTURES=2` and
  `RELEASE 576 STRICT CSRF BROWSER CHECKS PASSED`.
- `ISOLATED_STRICT_CSRF_BROWSER=PASSED` and full backend success.
- Zero dependency drift and isolated restore success.
- `TRACKER RELEASE DEPLOYMENT SUCCESS` and `EXIT_STATUS=0` at the exact
  candidate SHA, with no application restart.

All of these are **required observations**, not claims of results at
candidate-commit time.
