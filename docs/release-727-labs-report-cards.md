# Release 727 — Readable Labs report cards on phones

**Exact DEV base**: installed Release 726 at `2f9f15f11f807e4574143c49640ed62071e57df5`.

The saved Labs reports table previously required horizontal scrolling on a
phone. Keep the **same canonical table and row IDs**, but attach Tracker's
established `ux673-card-table` style, which renders rows as mobile cards
below 760px while preserving the desktop table. Existing four column
headers, search, sort, empty state, date links and filter dataset attributes
stay present. Add `data-label` to each cell and make the date report link
an accessible 44px touch action using the established card rules.

This touches only the Labs template (no new CSS, JS or data structures).
Qualified scopes include Labs read-only API/SQL checks, the original browser
filter and sort tests, responsive 320/390/430/760/1024 Chromium views across
light/dark and densities, and navigation regression. No full suite or PROD.

**Promotion order**: prepare and commit this release immediately, but do
not queue a DEV qualification/install that could replace DEV Release 726
until its explicitly authorized PROD promotion is completed or resolved.
The guarded PROD preflight for Release 726 is a separate critical path.
