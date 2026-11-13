# Release 594 — Food and vendor pricing signed CSRF workflows

Base: Release 593 `c52783e338bf0d46a3e9d8e45031a3ec860426ff`.

This is a conservative, consolidated first batch for the two food and
vendor-pricing workstreams, with **10 positive signed browser witnesses**
in the existing mandatory full strict Chromium gate.

- Food: water create/delete, food entry create/delete, and nutrient target save.
- Vendor pricing: shipping rule save/delete and manual offer
  create/edit/delete.

Each path is exercised through a real same-origin browser fetch with
signed `X-Tracker-CSRF`, and a separate API-context unsigned request
must receive 403. The tests inspect the originating request and the
initial route's strict CSRF report header; redirecting form handlers use
an explicit scoped Playwright response waiter so a final redirected
page cannot disguise a failing POST. SQLite reads verify saved quantities,
dollar-to-cent conversion, food nutrition targets and deletions inside
the explicitly checked disposable `/tmp/tracker-browser-qa.*` test DB.
Both HTTP and HTTPS are mandatory.

The readiness source inventory and gap planner list these 10 routes as
*source-only witness candidates*. Assuming the unchanged 144-route ledger,
the report should show **60 source candidates and 84 still lacking source
evidence**. Its manifest has 47 explicit routes. The other food and vendor
endpoints remain unqualified for global enforcement; in particular,
multipart upload/import paths need distinct signed multipart and data
integrity browser tests. No app production files, middleware, CSRF
settings, runner behavior, migration or release scripts are changed.

Full DEV qualification must pass before these new browser witnesses
are runtime-verified. The source planner is not runtime evidence;
global CSRF stays report-only. Promote with the existing guarded
dry-run and authorized execute only after DEV succeeds.
