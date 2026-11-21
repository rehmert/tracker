# Release 734 — Regimen action-button parity

Verified DEV baseline: Release 733 `28003549a8d0d69ac7ea23d8addd699a71a5a226`.

## Problem

Release 733 used custom `<summary>` CSS for **Edit medication**, while
**Delete medication** was a native form `<button>` with Tracker global
button rules. Their border, radius, padding, weight, background and
decorative disclosure arrow did not match.

## Correction

One shared `reg734-macd-action` style applies to the original native
Edit summary and Delete/Archive/Stop buttons. The disclosure caret is
removed from Edit so both action types use the same appearance.
All have min 44px touch height and matching hover/focus states.
The original disclosure form opens and closes without saving.
Delete remains a separately confirmed POST; no new JS, routes, DB
changes or migrations.

## Qualification

Exact-SHA isolated PrivateNetwork DEV qualification, source allowlist,
impact preflight, Jinja parse and source assertions. Chromium compares
actual computed styles between Edit, Delete and Archive in both
color schemes at 320/390/760/1024 widths, checks edit open/close,
44px touch targets and no overflow. Existing Release 733 and
732 regressions included; adjusted a legacy single-class expectation.
No full suite.

DEV installation only after verified qualification receipt. PROD
remains at Release 727 until independently approved.
