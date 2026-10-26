# Tracker Release 3.2 — Protocol layout and Today dashboard

## Changes
- Protocol editor frequency count and period are laid out in a dedicated flex container; the Remove action has a separate fixed-width column. The table scrolls horizontally on narrow screens instead of overlapping controls.
- Overview includes a Today dashboard with today's planned/recorded administrations, the next seven days of projections, five recent recorded administrations, and the five soonest inventory depletion estimates.
- A missing protocol start date is flagged with a link to the protocol editor.
- Existing calendar same-day, same-compound reconciliation is reused. A match does not verify dose equivalence. The Today section is read-only and never creates dose logs or changes stock.
- Light and dark modes use existing theme variables.

## Deployment
1. Back up SQLite and uploaded files.
2. Deploy the updated application while retaining `.env`, `data/`, and uploads.
3. Restart the Tracker service and hard-refresh Chrome (Ctrl+Shift+R).
4. Check the Protocol editor on desktop and narrow viewports, and the Overview Today cards.

No schema migration is required for this release.

## Validation
`python -m pytest -q` — 59 passed.
