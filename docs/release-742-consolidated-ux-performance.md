# Release 742 — Combined outstanding CSS, mobile navigation and read-performance cleanup

Base: Release 741 DEV/PROD/main exact `c5efed6b40f4324187eff3e83dbed44d9e68f5c4`.
One change-scoped integrated release on `release/742-consolidated-ux-performance`.

## Changes
- **Supplies:** consolidate three page-specific CSS assets to one file, in
  original cascade order. Keep historical source styles in Git. Add an accessible
  Stock / Create category / Manage categories / Reconcile Stock shortcut bar
  on the long inventory page. No new write paths or permission changes.
- **Calendar:** consolidate five page-specific CSS assets to one, preserving
  original rules and cascade. Retain the existing five JavaScript activities and
  Release 741 MACD stylesheet. No scheduled-dose logic changes.
- **Inventory read performance:** Fetch only the ten most recent purchases
  for the Supplies shortcut row in SQL, not the complete purchase table.
  The HTML continues to show the same ten records in the same order.
- **Notes read performance:** Eager batch-fetch Notes sources and compound
  associations for list/search views to avoid per-Note lazy-load queries.
  Preserve search, tag, compound, source and saved-view behavior.

## Qualification
- Exact-SHA ancestry, clean Release 741 DEV baseline, private-network
  disposable worktree and SQLite database, Release 604 asset impact review.
- Syntax, import, Jinja parsing, CSS concatenation parity and HTML asset
  checks, actual rendered-HTML HTTP tests, bounded SQL query counts,
  Chromium 320/390/430/760/1024 in light/dark with keyboard and overflow
  checks; Release 741, Supplies, Calendar, Notes regressions.
- Full app-wide suite deliberately not run. No schema, dependency, release
  controller, auth or PROD changes; receipts stay sanitized in release branches.

## Scope boundary
This targets two high-use multi-CSS pages and targeted N+1/overfetch paths.
It does **not** claim global retirement of the many legacy stylesheets or
certification of every MACD action across the application. Further use-driven
fixes should be based on DEV hands-on testing.

**Promotion:** Qualify isolated → verified DEV install; separate explicit
authorization required for PROD preflight/deploy.
