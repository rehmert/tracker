# Release 736 — Restore chevrons on Regimen Add disclosures

## Problem

The Regimen Catalog Add control switched to a flex-based native `<summary>`
in Release 733. Chromium suppresses the default details marker on flex
summaries, leaving the Add control with no visible expand/collapse signifier.

## Fix

Explicit CSS-drawn chevrons are appended to **Add supplement or medication**
and **Add schedule** summary triggers, using `currentColor` so they remain
visible in dark and light themes. Native details semantics remain intact.
Chevron points down when collapsed and up when expanded; no JavaScript
or new server route is needed. Both Add controls retain at least 44px
touch height. The original Edit/Delete/Archive styling is unchanged.

## Scope and acceptance

Jinja source + actual Chromium computed pseudo-element checks at
320, 390, 760, and 1024px in light/dark mode; verify visible borders,
state change after click, native details expansion, and no overflow.
Regimen Edit/Delete tests included as focused regressions.
No app model, database migration, authentication or shared CSS changes.

Run isolated DEV qualification on exact SHA and install only with a
passed immutable receipt; no PROD promotion without separate approval.
