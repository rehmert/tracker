# Release 2 — Premium Dashboard

Built on Release 1 (Data Protection). No database migrations.

## What's new
- Three large, clickable overview cards for latest weight, blood pressure and pulse.
- Compact 30-day SVG sparklines drawn from actual recorded measurements only.
- Descriptive 30-day changes/averages where sufficient measurements exist.
- Subtle gradient on the weight card, softly rounded icon backgrounds, responsive layout.
- Consistent local SVG icons for inventory/spend/stock/COA metrics.
- Light and dark palettes are inherited from the existing theme system.
- Empty-data states display a dash and helpful text, rather than invented values.

## Deploy
1. Back up the current database and uploaded files (or create a verified backup in Tracker).
2. Extract the release over the application code, preserving `.env`, `data/`, backups, and uploaded files.
3. Restart with `sudo systemctl restart tracker.service`.
4. Hard refresh your browser (Ctrl+Shift+R).

## Scope
This is the dashboard visual refinement release. Universal search and dose-entry improvements are planned for Release 3. No third-party health-data integrations are included.
