# Release 520 candidate — multipart CSRF validation in optional strict mode

Base: Release 519 `21e270fb6e63d363abb335c299dca47ae3a66374`.

## Issue

Global CSRF enforcement already exists behind `TRACKER_CSRF_ENFORCE=1`.
The HTTP middleware intentionally does not parse `multipart/form-data`
because doing so there can consume uploaded file streams before the router
receives them. It reports `form-uninspected`, which previously caused
strict mode to reject even properly signed native HTML upload forms.

## Implementation

- Add the global FastAPI dependency `enforce_multipart_csrf520`. In ordinary
  report-only mode, it does nothing.
- Under explicitly enabled strict mode, the HTTP middleware continues checking
  normal header-token, JSON, and URL-encoded requests. Multipart submissions
  **without** a header are handed to the route dependency for verification.
- The dependency checks the browser's signed CSRF cookie against exactly one
  `csrf_token` form field in the cached `Request.form()`; duplicate or
  missing fields and mismatches are refused with HTTP 403. A valid signed
  `X-Tracker-CSRF` request header works for JS/fetch/HTMX uploads, without
  requiring an extra field. Unavailable signing keys fail closed.
- The dependency never calls `request.body()` on multipart uploads and
  leaves the parsed file handles for the endpoint to consume.
- Existing mandatory signed session-login/account CSRF and the DEV-only
  secondary-account mounted routes retain their own validation. In particular
  `/logout` is explicitly excluded from redundant global enforcement.

No database migrations, ORM changes, dependencies, systemd changes, or extra
network listeners are required. No default CSRF setting changes.

## Isolated tests

`tests/test_release520_csrf_multipart.py` covers report-only compatibility,
strict missing/tampered/duplicate tokens, native multipart field success,
header-based multipart success, invalid-header precedence, cross-origin denial,
real Labs CSV upload compatibility, JSON and URL-encoded behavior, and preserved
readability of uploaded files after the dependency returns.

All test requests run against disposable FastAPI/TestClient instances and a
temporary CSRF signing-key directory. No real uploads or DBs are touched.

## DEV-only acceptance

1. Qualify the exact branch SHA using the regular guarded DEV LXC pipeline.
   Require the complete backend suite, browser qualification, isolated
   backup/restore, and runtime smoke with `EXIT_STATUS=0`.
2. On DEV, separately exercise the **strict-mode browser compatibility matrix**
   against an isolated instance/fixture: native uploads (Labs report, CSV
   import, COA), URL-encoded forms, JS fetch, HTMX, logout/account settings,
   and secondary-account signed forms. Include intentionally missing and
   forged CSRF tokens, with no unintended data writes.
3. Do **not** enable `TRACKER_CSRF_ENFORCE=1` on PROD as part of installing
   this code. DEV browser compatibility must be proven before enabling strict
   mode system-wide. No credentials or signing keys should be copied between
   DEV and PROD.

GitHub is version control **only**. No GitHub Actions, external CI, or hosted
tests.

## Remaining work

This release closes the multipart parsing/verification gap in the opt-in
strict mode. It does **not** claim complete browser compatibility across every
legacy form, nor does it change the secure default from report-only to global
enforcement. Full strict-mode activation remains gated by issue #9 and the
existing source and browser inventory scripts.
