# Release 574 — dynamic-form route-shape audit and expanded strict-browser matrix

## Starting point

Release 573 `edaadc67ee36aa32c0f8bc01f011ec2d82325a6c`
has been reported fully deployed to PROD, and repository `main`
was verified at the same SHA. DEV also passed guarded Release 573
qualification, including a strict-CSRF disposable candidate.

The Release 573 route inventory reported:

| Metric | Release 573 |
| --- | ---: |
| Unsafe runtime routes | 144 (136 POST, 5 DELETE, 3 PUT) |
| Static/runtime mismatches | 0 |
| Root global dependency gaps | 0 |
| File-upload write routes | 11 |
| Static native/HTMX write sites | 101 |
| Literal browser actions matched | 33 |
| Literal actions unmatched | 0 |
| Static entries requiring manual review | 68 |
| JS request callsites needing review | 46 |

These figures do not prove all write endpoints are safe to use with
global CSRF enforcement. Do not enable `TRACKER_CSRF_ENFORCE=1` based
on these source-only statistics.

## Bundled changes

1. **Safer static classification of Jinja-generated actions.** The
   `scripts/tracker_csrf_inventory572.py` audit now matches a full
   Jinja path segment such as `{{ p.id }}`, `{{ v.id }}` or
   `{{ e.product_id }}` to a registered route parameter, but only
   when the HTTP method, number of path segments and all literal
   segments agree. It never evaluates templates or interpolates IDs.
   Template expressions involving operators, unrecognized filters,
   dynamic queries/fragments, entire dynamic actions and mounted
   routes remain manual/unresolved.
2. **New inventory metrics.** The JSON now distinguishes
   `templated_route_shapes_matched` from
   `browser_targets_unresolved_without_shape_match`. A shape match
   **still contributes** to `browser_writes_needing_manual_resolution`,
   because rendering, token injection and form submission are not
   verified by source matching.
3. **Static regression tests.** `tests/test_release574_csrf_dynamic_shapes.py`
   covers single/multi-ID segments, mismatched methods, unrelated
   routes, dynamic template logic, filters and external targets.
4. **Expanded real strict-mode browser coverage.** The existing
   guarded disposable Chromium matrix gains native signed-token checks
   for Vendor Prices, Labs creation, COA creation and Page editing
   entry points over local HTTP and host-rewriting HTTPS.
5. **Real rendered dynamic-form negative proof.** A disposable
   compound fixture's Jinja-rendered deletion form must have exactly
   one matching signed CSRF field, and an otherwise identical unsafe
   POST without a token must be denied before mutation. There is **no**
   legitimate destructive POST in this test.
6. **`fetch(Request)` positive proof.** A browser-created
   same-origin `Request` object, rather than a URL/options fetch,
   must receive the signed header under strict mode on HTTP/HTTPS.
   An empty required compound name deliberately returns 422 after
   CSRF validation without creating user data.

All HTTP requests and browser mutations run against the runner's
existing `/tmp/tracker-browser-qa.*/data` disposable candidate.
No installed DEV/PROD service, live user data or external browser
endpoint may be used by these tests.

## Release and safety properties

- No database migrations, dependency changes, systemd changes, user
  permission changes or new network listeners.
- No changes to `TRACKER_CSRF_ENFORCE`, signed session auth,
  `app/csrf_reporting.py`, origin middleware or routes themselves.
- The changes affect source-only inventory, documentation and tests:
  the guarded release runner should see no `app/` source changes
  and should avoid an unnecessary Tracker service restart.
- Existing Release 520/521/522/573 strict-CSRF tests remain mandatory.
- The Release 574 candidate must pass focused tests **before** invoking
  the normal guarded DEV release. The full backend/browser and
  isolated restore suite must pass, followed by the dependency audit
  with 44 installed packages and zero drift.
- PROD promotion requires signed DEV approval through
  `scripts/tracker_promote568.py`, with exact-base checks. GitHub
  remains version control, never a deployment executor.

## Manual review still required for Issue #9

The static triage reduces ambiguity about *which registered route*
a template may target. It does not automatically close the 68-form
review obligation or the 46 JavaScript callsites.

Remaining work includes positive strict-mode submissions for the
other native/multipart workflows, account and secondary mounts under
their own signed CSRF system, unusual large or streamed body paths,
and a separately approved, reversible live DEV strict-mode rehearsal.
Do not enable global strict mode on PROD as part of this release.
