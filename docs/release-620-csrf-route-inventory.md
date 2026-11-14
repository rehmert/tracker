# Release 620 — conservative CSRF unsafe-route inventory

Base: Release 619, `66ab557a48c352f631c513eb222040f8008de604`.

## Change

Add an offline, read-only AST inventory of declared unsafe HTTP route
handlers in `app/**/*.py`. Each entry gives file, line, handler, route,
methods, and whether the body mentions "csrf"; **every entry requires
manual review**. The source inventory deliberately does not claim that
a handler is protected merely because it mentions CSRF.

```sh
/opt/tracker/.venv/bin/python /opt/tracker/scripts/tracker_csrf_route_inventory620.py
```

This emits JSON to stdout. Redirect to a file only if desired.
No HTTP requests, changes to application data, or service mutation.

**Limitations:** Static decorator parsing does not resolve mounted apps,
router prefixes, dynamically registered endpoints, dependencies, template
form coverage, proxy settings or effective authentication/CSRF behavior.
Nested registration and runtime-generated routes need follow-up auditing.
It is an issue #9 *evidence-gathering aid*, not completion of issue #9.

The existing issue #10 dependency manifest/constraints remain in place
and unchanged. This release does not install, pin, or upgrade anything,
and does not establish fresh-environment reproducibility.

## Acceptance

- New tests detect POST/PATCH/DELETE, suppress GET, and flag dynamic routes.
- Full guarded DEV qualification remains mandatory, including isolated
  HTTP/HTTPS strict-CSRF browser tests and installed-commit verification.
- The original interactive release runner, 16-workers, 16GiB ceiling and
  DEV-controlled signed PROD promotion are unchanged.
- Global `TRACKER_CSRF_ENFORCE` remains opt-in. No schema or middleware
  changes, and no PROD activity without approved promotion.
