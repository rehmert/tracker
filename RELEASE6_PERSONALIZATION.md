# Release 6 — Personalization and CSV exports

Based on Release 5. No database migration required.

## Features
- Overview: Customize dashboard button. Hide/show and reorder sections with arrows. Preferences stored locally in the browser (localStorage). Reset restores defaults.
- Search filters on supported tables are remembered per browser tab/session (sessionStorage).
- Keyboard shortcuts: Alt+1 Overview, Alt+2 Doses, Alt+3 Vitals, Alt+4 Supplies, Alt+5 Exports. Ctrl+K universal search remains.
- Exports: CSV downloads for vitals, doses, vials, supplies, purchases, and compounds. Data is exported in original stored units (e.g. weight_kg, cents). CSV text fields beginning with spreadsheet formula characters are escaped.

## Deploy
1. Use the Backups page to make and verify a backup.
2. Replace application files, preserving .env, data/, and uploaded files.
3. Restart: sudo systemctl restart tracker.service
4. Chrome: Ctrl+Shift+R.

## Limitations
- Layout preferences are per browser, not synced.
- CSV export is not a restore mechanism; use Release 1 backups for full recovery.
- Automatic supply consumption per dose is not included in this release. It requires opt-in supply mapping, safe stock validation and rollback semantics and should be implemented separately.
