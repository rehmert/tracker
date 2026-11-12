# Release 573 — bundled CSRF header hardening, form coverage, and route triage

**Base:** DEV-qualified Release 572 `eb7655c6406bb16684c5b6b8b765894d240d5854`.

**Production baseline:** Release 571 `9b66c99ba3f5ddb98671955998afb8d55f144820`
remains the latest independently verified PROD release as of preparation.
GitHub `main` also remained at Release 571. Release 572 does not
have to be promoted separately: Release 573 descends from it and the
existing DEV-controlled promotion checks PROD's actual installed base
before any push.

## Bundle contents

1. **Unambiguous CSRF headers** — `app/csrf_reporting.py` treats multiple
   `X-Tracker-CSRF` headers or an explicitly blank header as invalid.
   Previously, the generic header reporter could consider one header
   value valid; the multipart dependency had stricter duplicate handling.
   A supplied header now always takes precedence over a form field.
   Multipart upload streams are still never parsed in HTTP middleware.
2. **Origin and browser metadata hardening** —
   `app/request_origin.py` rejects duplicate Host, Origin and
   Sec-Fetch-Site headers on unsafe requests, while preserving GET,
   HEAD and OPTIONS behavior. `app/proxy_origin522.py` also rejects
   those duplicates before permitting a signed TLS Host-rewrite
   exception. These checks prevent ambiguous header selection between
   proxies and the application.
3. **Disposable integration coverage** —
   `tests/test_release573_csrf_header_defense.py` covers report-only
   compatibility, strict rejection of mixed/duplicate/blank headers,
   signed single-header acceptance, large URL-encoded bodies with a
   header, HTTP origin mismatches, and proxy-exception behavior.
4. **Real Chromium HTTP + HTTPS matrix** —
   `tests/browser/test_strict_csrf521.py` adds native signed-token
   checks for POST forms across Compounds, Vials, Purchases, Supplies,
   Vitals, Blends, Food, and Protocols (both local HTTP and host-
   rewriting HTTPS). It tests same-origin signed JavaScript fetch
   reaching ordinary validation and unsigned writes being rejected.
   The existing browser-qualification runner already collects this
   test file under disposable strict mode.
5. **Action-to-route review inventory** —
   `scripts/tracker_csrf_inventory572.py` now classifies literal
   native form and HTMX actions against actual registered unsafe
   routes, with explicit manual-review categories for dynamic,
   missing, relative, cross-origin and unregistered targets. It
   retains JavaScript callsites in the inventory JSON. The audit
   remains an imperfect source heuristic, not security certification.
   `tests/test_release573_csrf_inventory_review.py` tests these
   classifications.

## Security-policy scope

- **No change** to the default `TRACKER_CSRF_ENFORCE=0` on installed
  DEV or PROD. The browser runner enables strict mode only on
  disposable candidate servers.
- **No change** to DB schema, ORM, requirements, systemd unit,
  user permissions, source-controlled secrets or session-auth tokens.
- Application middleware changes mean the guarded DEV/PROD
  release runner will restart Tracker as needed. Signed Host-rewrite
  exceptions, strict native upload routing, and existing session
  CSRF validation must continue to pass.
- The broader negative checks do **not** establish that every legacy
  write is functional in strict mode. Issue #9 remains open pending a
  complete positive-write inventory, DEV policy rehearsal, and
  explicit operator approval for any PROD policy change.

## DEV qualification requirements

Qualify exactly the release branch SHA, using the currently installed
Release 572 as the DEV base. Run the focused test modules in a
disposable detached worktree, then run the guarded DEV runner with
`--instance DEV --base <release-572-sha> --target <candidate-sha>`.
The runner must report:

- `ISOLATED_BROWSER=PASSED`
- `ISOLATED_STRICT_CSRF_BROWSER=PASSED`
- `=== ALL BACKEND TESTS PASSED ===`
- `=== ISOLATED RESTORE VERIFICATION PASSED ===`
- `EXIT_STATUS=0`, followed by the exact `DEV_QUALIFIED_COMMIT`.

Generate the enhanced runtime audit from the installed exact commit
with a new disposable `/tmp/tracker-csrf572.*/data` directory and
copy only its JSON to a root-owned, mode-0600 qualification record.
Require no root FastAPI dependency gaps and report all unmatched
or dynamic browser entrypoints for manual examination.

**Promotion:** After DEV passes and an operator reviews the inventory,
use the existing signed DEV-controlled promotion controller. Supply
the verified actual PROD base commit; do not assume Release 572
was installed on PROD. The controller performs a preflight
before GitHub main is advanced or PROD is changed. Do not
turn on global strict CSRF as part of this promotion.

## Remaining Issue #9 work

Review the action-to-route triage and unsupervised JavaScript callsites;
add positive browser write cases for every untested high-risk path,
including oversized body, CSV import, backup upload, password/account,
and secondary mount workflows. Finish an independent DEV strict-policy
configuration and rollback rehearsal before requesting an opt-in PROD
policy change.

Issue #10's local 488 MB archive remains protected through the
operator's 15-minute LXC snapshot/replication policy; no additional
backup-copy workflow is required by this release.
