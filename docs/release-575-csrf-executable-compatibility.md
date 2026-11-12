# Release 575 — executable CSRF compatibility for dynamic forms and JS review

**Starting point:** Release 574
`7d4e0c987f4dd1cac9db776fad6a36746f59b2bf`
was DEV-qualified and PROD-deployed, with GitHub `main` at the
same SHA. No installed strict-CSRF enforcement change is approved
by Issue #9.

## Scope of this bundle

1. **Real mobile quick-entry write:** The existing disposable strict
   Chromium suite now visits the mobile view in a narrow viewport,
   inspects the three implicit-action forms (Weight, Blood Pressure,
   Water), verifies they each have exactly one signed field, and
   performs an actual Water write via the application's fetch/FormData
   interception. It verifies the response's signed report and the
   outgoing `X-Tracker-CSRF` header. Both HTTP and host-rewriting HTTPS
   paths are exercised.
2. **Notes create/edit Jinja action:** A new disposable page is created
   through the real HTML form, then its generated `/pages/{id}`
   editing action is inspected and used for an authorized edit.
   A forged edit is denied before mutation. This tests the
   conditional template action that source matching could not resolve.
3. **COA create/edit Jinja action:** A new disposable certificate is
   created against the browser runner's fixture vial, then the
   `/coas/{id}/edit` multipart form is verified and submitted with
   signed proof. A forged multipart update is denied. Both HTTP
   and HTTPS flows are tested; no real attachment or user record
   is accessed.
4. **Signed session login compatibility:** The independently signed
   session login remains permitted with its proper CSRF token when
   the global strict flag is on (including the TLS Host-rewrite
   scenario). Missing session tokens remain forbidden.
5. **Review all 46 JavaScript source callsites:** New read-only
   `scripts/tracker_csrf_js_review575.py` enumerates all 46
   fetch/HTMX source callsites from the existing CSRF source scanner.
   It reports approximate nearby literal HTTP method hints,
   retaining `dynamic`, `unknown` and `HTMX` review categories.
   Every entry remains an **unreviewed runtime effect** until executable
   browser acceptance validates it. The tool never uses live
   credentials, data, or network access, and only permits a private
   JSON output in a new `/tmp/tracker-csrf575.*/` directory.

## Limits: what this does not prove

- The three mobile forms are token-inspected, but only Water is
  submitted as a positive write in this release.
- The `preparation_edit.html` implicit-action form still requires
  a disposable preparation event and an authorized correction test.
- Some JS callsites are read-only GET requests, some are unsafe
  requests, and others are method-dynamic; short source excerpts
  cannot establish real runtime behavior.
- All 144 registered unsafe routes still need end-to-end coverage
  assessment; structural dependency presence is not a security
  certificate.
- Secondary mounted account workflows use separate signed token
  checks. Existing isolated tests protect them, but their
  compatibility with a live DEV global strict policy requires
  separate qualification.
- This release does **not** change the application, dependency pins,
  database, deployment mechanism, service environment, or
  `TRACKER_CSRF_ENFORCE` setting. No installed application restart
  is expected for this tooling/tests-only release.

## Qualification and deployment

Run the new focused source/test modules plus existing security and
CSRF regressions in a disposable Release 575 worktree before the
guarded DEV release. The existing Release 521/574 strict Chromium gate
automatically collects these new browser tests. Require the complete
backend/strict-browser/restore gates and a zero-drift baseline before
declaring Release 575 DEV-qualified.

After DEV succeeds, create a private JS callsite report using:

```bash
sudo bash <<'BASH'
set -Eeuo pipefail
[[ "$(hostname -s)" == tracker-dev ]] || exit 1
cd /opt/tracker
DIR=$(mktemp -d /tmp/tracker-csrf575.XXXXXXXX)
trap 'rm -rf -- "$DIR"' EXIT
.venv/bin/python scripts/tracker_csrf_js_review575.py \
  --json "$DIR/js-review.json"
install -m 600 "$DIR/js-review.json" \
  /etc/tracker-release/release-575-csrf-js-review.json
BASH
```

The report must contain all 46 callsites. It does not authorize
strict mode. PROD promotion remains a separate signed,
operator-controlled DEV action through
`scripts/tracker_promote568.py`.

## Outstanding Issue #9 work

- Construct a disposable prepared vial fixture to test
  `preparation_edit.html` positive correction under strict mode.
- Test positive Weight and Blood Pressure quick entry, not merely
  token injection.
- Resolve the JS callsite review categories with specific
  executable positive/negative browser cases, prioritizing
  actual unsafe HTTP methods.
- Exercise secondary accounts, login, uploads and proxy-origin
  cases with strict mode under a truly reversible DEV operating
  configuration, then separately approve any PROD policy switch.
