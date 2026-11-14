# Release 610 — Vendor Price Comparison clear filters

Base: Release 609 `88d5ca98841642502d704e96e39f8c9cf1dda41b`.

The Vendor Price Comparison screen now includes a **Clear filters** button.
It is disabled when the compound selector is set to All compounds, the
vendor-name search is blank, and the page size remains 25. When activated,
it clears both filters, restores 25 offers per page, resets the displayed
page to the first, refreshes the live match count and pager, and moves
keyboard focus to the vendor-name search. Search, sort, offer-edit and
delete operations otherwise remain unchanged. Existing sorted row order
is intentionally preserved.

The isolated Chromium fixture covers resetting both combined filters,
returning from the All page-size option to 25, focus behavior, and the
disabled state at 320, 390 and 1024 pixels. This adds no persistence,
network requests, database/schema work or new authorization paths.

Use the existing guarded DEV release runner, including strict HTTP/HTTPS
browser checks, full backend tests, verified backup/restore, and preserved
root-only qualification evidence. Perform manual DEV acceptance, read-only
signed PROD promotion preflight, and explicit promotion separately.

Mandatory resources remain 16 backend pytest workers with
`--dist=loadfile` and `MemoryMax=16G`; no test or security bypass.
