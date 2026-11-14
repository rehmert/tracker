# Release 621 — Static HTML/HTMX CSRF audit crosswalk

Base: verified Release 620, `8389b4c4e9c2df8132c4c1352659496ec5d76df0`.

## Purpose

This increment extends Release 620's read-only unsafe-handler declaration
inventory with a static crosswalk to HTML forms and HTMX write attributes.
The source auditor enumerates `method=POST/PUT/PATCH/DELETE` on native forms
and `hx-post`, `hx-put`, `hx-patch` and `hx-delete` on HTML tags in
`app/templates/**/*.html`. It compares literal URL paths to statically
declared unsafe handlers and reports candidate source references for review.

### Read-only command

```sh
/opt/tracker/.venv/bin/python /opt/tracker/scripts/tracker_csrf_form_crosswalk621.py
```

The result is structured JSON with total unsafe handler declarations,
visible template write controls and candidate matches. No requests,
authentication operations, database queries, credential reads, or writes
are performed. No output file is created by default.

Every entry has `review_status=MANUAL_REVIEW_REQUIRED`; candidate matches
**are not** evidence of effective CSRF protection. Unmatched entries are
**not** proof of vulnerability. Runtime registration, middleware,
router prefixes, JS-based actions, secondary apps, runtime Jinja
rendering and dynamically generated controls require separate review.

## Safety

- Existing auth, Origin guard, proxy handling, signed CSRF policy, and
  default `TRACKER_CSRF_ENFORCE=0` are unchanged.
- No migration, dependency change, install, package upgrade, service
  restart, or PROD mutation is part of this source-only change.
- Issues #9 and #10 remain open. This is evidence collection for #9,
  not strict-mode enablement or dependency reproducibility.
- Preserve the original interactive guarded DEV runner, full suite,
  isolated HTTP/HTTPS tests, 16-workers, and the existing memory policy.
- PROD promotion requires qualification receipt, preflight,
  operator approval and signed `--execute`.
