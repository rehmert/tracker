# Release 572 — Strict-CSRF route inventory and negative coverage

## Purpose

Issue #9 cannot safely be closed just because a handful of browser
workflows pass with `TRACKER_CSRF_ENFORCE=1`. Tracker has many older
native forms and write routes, some behind a host-rewriting HTTPS proxy.
The existing Release 520/521/522 security layers, report-only defaults,
origin guard and signed session authorization are **unchanged**.

Release 572 adds:

- `scripts/tracker_csrf_inventory572.py`: a source/runtime comparison
  of unsafe POST/PUT/PATCH/DELETE `APIRoute` registrations, including
  optional mounted FastAPI subapplications when actually enabled. It
  reports structural FastAPI authentication and multipart CSRF
  dependencies, body field types, session-signature exceptions,
  file-upload endpoints, and gaps against the existing static
  `scripts/tracker-csrf-readiness.py` scan.
- `tests/test_release572_csrf_inventory.py`: validates the inventory
  against real application routes and synthetic unprotected/mounted apps.
- `tests/test_release572_csrf_negative_matrix.py`: enables strict mode
  **only inside a disposable TestClient**, then attempts untrusted writes
  against every registered root-application unsafe route, verifying that
  each request is rejected with HTTP 403 before endpoint handling.
  It also exercises missing/forged tokens and a signed-token request
  from a foreign origin.

The existing browser runner still tests native HTTPS uploads (Labs and
COAs), HTMX, JavaScript fetch, native compounds/vitals forms and signed
session flows. This release does not remove or weaken that coverage.

**No changes** to `app/`, `requirements*.txt`, database tables,
installed service environment, security policies or deployment scripts
are included. Installing Release 572 does **not** activate strict CSRF.

## DEV-only inventory command

Run in a detached source/test sandbox after the guarded Release 572
DEV qualification. The inventory requires a disposable data path, not
`/opt/tracker/data` or any installed Tracker data path.

```bash
sudo bash <<'BASH'
set -Eeuo pipefail
[[ "$(hostname -s)" == tracker-dev ]] || exit 1
RUN=$(mktemp -d /tmp/tracker-csrf572.XXXXXXXX)
trap 'rm -rf -- "$RUN"' EXIT
mkdir -m 700 "$RUN/data"
cd /opt/tracker
TRACKER_DATA_DIR="$RUN/data" PYTHONPATH=/opt/tracker \
  .venv/bin/python scripts/tracker_csrf_inventory572.py \
    --json "$RUN/registered-unsafe-routes.json"
echo "=== Read-only summary was generated in the disposable sandbox ==="
BASH
```

To keep the full inventory for manual audit, adjust the procedure to
copy the JSON into a separate root-only operator-controlled location
before the disposable directory is removed. Do not store credentials,
live request payloads, or session tokens in inventory output.

## Limitations and rollout gates

The HTTP 403 matrix proves **fail-closed missing-token behavior** across
registered root routes when strict mode is enabled. It does not test
positive/legitimate form behavior for every endpoint. Those are distinct
requirements for safe rollout.

Even the runtime inventory cannot prove that every route has correct
endpoint authentication or that every dynamic submission has a valid
signed hidden form field. Mounted secondary accounts have their
own signed-CSRF logic and are not part of the root-route negative matrix.
The comparison must be repeated with every relevant optional DEV-only
mounted-feature configuration.

Before changing `TRACKER_CSRF_ENFORCE`:

1. Review each runtime write route with its auth/session, token and
   origin/proxy semantics; inspect static inventory differences.
2. Expand **positive** native browser and multipart coverage for every
   remaining write path and test representative malformed tokens,
   session failures, cross-site writes, duplicate form fields and proxy
   Host rewrites.
3. Document and safely handle any oversized URL-encoded/streaming
   bodies, clients lacking a cookie, and any unusual content types.
   The current strict middleware intentionally fails closed for
   `form-uninspected` non-multipart requests.
4. Qualify explicit DEV strict policy configuration under a separate
   operator-approved change with a verified, reversible environment
   backup. Only consider PROD after observed DEV behavior is correct.

An inventory is not a security certification. Do not infer that a lack
of structural dependency gaps means CSRF enforcement is universally
compatible. Leave GitHub for source history and review, not CI or
automated deployment.
