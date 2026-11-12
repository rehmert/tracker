# Release 578 — CSRF route evidence, conservative JS attribution, browser matrix

Release baseline: `71fd42d6abb75beb392d3c1d2874df050dd0ad07` (577).
Issue #9 remains open. **No installed global strict-CSRF enforcement change.**
No application feature files, database migration, requirements or systemd units
are changed. The production release path remains signed and DEV-controlled.

## Bundle

1. `scripts/tracker_csrf_route_ledger578.py`: deterministic, read-only
   ledger of *every* unsafe route declared by the existing scanner, all
   native HTML/HTMX write sites, and all 46 JS request callsites identified
   by prior releases. It identifies only exact syntactic method+literal-path
   source pairs. A literal URL that matches a parameterized route is recorded
   as a possible path candidate; it is never treated as executed or cleared.
   Dynamic and implicit write paths remain unresolved.
2. `tests/test_release578_csrf_route_ledger.py`: inventory preservation,
   source provenance, URL-pattern ambiguity, dynamic interpolation rejection,
   stable output, zero false clearance, and private-report contract.
3. `tests/browser/test_strict_csrf521.py`: add **20 parametrized** negative
   Chromium scenarios against the private disposable candidate:
   - Twelve native POST request cases over HTTP and HTTPS: missing or
     forged token, hostile Origin with/without valid token, hostile Origin
     without Fetch Metadata, and tampered signed token.
   - Eight unsafe method probes (POST/PUT/PATCH/DELETE, HTTP/HTTPS).
     A 405 for an unimplemented verb is *not* counted as CSRF protection.
   These extend earlier signed positive write, multipart, JSON, HTTPS reverse
   proxy, preparation correction, login, and secondary-session tests.
4. Retain the automatic DEV qualification-log handoff introduced in 577.
   Release 578 is the first release using that runner on DEV. A successful
   worker should automatically preserve a root-only receipt at
   `/etc/tracker-release/release-578-dev.log` without operator copying.
   The signed promotion preflight must still verify the receipt independently.

## Interpretation and remaining blockers

The route ledger is **an honest inventory, not a measured pass rate**.
All JS callsites remain unverified *as individual JS executions*, and
all routes remain unqualified *in this ledger*, even though existing browser
suites verify selected actual write paths. This avoids inventing per-route
evidence from unrelated tests. The operator can prioritize remaining work
by source module, source line, unresolved method, literal route hints,
and native implicit action. Later releases should attach direct executable
evidence to the exact routes before claiming clearance.

Strict-CSRF live DEV rehearsal (including real secondary-account behavior),
complete dynamic JS callsite traversal, all 144 unsafe routes, request-body
limit tuning, and any production enforcement are **not** authorized here.

## Read-only report

Run in an isolated candidate worktree, not against installed PROD:

```bash
dir=$(mktemp -d /tmp/tracker-csrf578.XXXXXXXX)
.venv/bin/python scripts/tracker_csrf_route_ledger578.py --json "$dir/ledger.json"
```

The report contains file paths/line numbers, route patterns, classifications
and no user records, credentials, request payloads or session tokens.

## Guarded qualification and promotion

Run `tracker-release.sh --instance DEV` with the pinned exact Release 577
base and Release 578 target. This executes compileall, Jinja parsing,
browser qualification on isolated HTTP and HTTPS with strict=1 in the
candidate process, full backend tests, backup/restore verification and
post-install checks. Verify both the guarded success marker and the
automatic receipt, then perform a separate DEV UI review.

Run `tracker_promote568.py` **without** `--execute` first. Only after
a passed preflight and explicit human production approval may the same
command run with `--execute`. PROD must remain on report-only CSRF.
