# Release 623 — consolidated static CSRF review queue

Verified production baseline: Release 622 at
`429d828ec01f8f63867de20acf45526e134043fe`.

## What changed

A new read-only source-audit command combines the existing Release 620
unsafe route declarations, Release 621 native HTML/HTMX write-control
crosswalk, and Release 622 JS request-call candidates into a
deterministically sorted JSON review queue.

```sh
/opt/tracker/.venv/bin/python /opt/tracker/scripts/tracker_csrf_review_queue623.py --limit 25
```

Omit `--limit` for all findings. Counts in `totals` always cover the
entire source inventory, even when only the first N findings are shown.
Output goes to stdout; the command does not read the Tracker database,
send requests, or write files.

- **P1:** unresolved/dynamic template destinations and JS methods;
  inspect uncertain request construction first
- **P2:** static template matches and identified JS write-method hints;
  verify signed tokens, auth and same-origin protections
- **P3:** declared unsafe routes not matched by literal template actions;
  reconcile with JS, mounted apps, client APIs and runtime registration

The P labels indicate **review order only**, not exploitability,
risk severity or evidence that a route is protected. All records retain
`MANUAL_REVIEW_REQUIRED`. Source scanners are intentionally incomplete,
can produce false positives and do not replace HTTP/HTTPS browser
negative tests and multipart/legacy-form review.

## Guardrails

- No changes to security middleware, origin protections, strict-CSRF
  setting or default, runtime web forms, application database, models,
  migrations, dependencies, service configuration, or deployment tools.
- This is partial evidence-gathering for open issue #9, **not** a
  completed security audit or authority to enable strict enforcement.
- Issue #10 still requires a separately reviewed reproducibility path.
- Preserve original interactive DEV qualifier with focused regression,
  full 16-worker backend suite, isolated HTTP/HTTPS browser gates,
  verified recovery archive and exact SHA receipts.
- PROD promotion is subject to DEV qualification, manual approval and
  the existing signed promotion preflight and `--execute` sequence.
