# Release 3 — Everyday Usability

Built on Release 2 Premium Dashboard. No database migration.

## Included
- Ctrl+K (or Cmd+K) command palette; local search across compounds, vials, protocols, purchases and lab reports. Quick actions for doses, vitals and purchases.
- Search results are escaped through DOM text nodes and queries are parameterized SQLAlchemy expressions. Minimum 2 characters, maximum 100.
- Toast confirmations for successful HTMX form submissions, and request errors.
- Dose form remembers the most recently selected vial and injection site in browser localStorage; does not remember dose amount or timestamp. Existing live dose preview and inventory checks remain intact.
- No external metrics integrations or network services.

## Deploy
Back up the database and uploads first. Deploy the application while preserving `.env`, `data/`, and uploads. Restart `sudo systemctl restart tracker.service` and hard-refresh Chrome (Ctrl+Shift+R).

## Notes
- The existing dose form is preserved intentionally, including conversion preview, vial remaining validation, and edit/delete.
- The command palette searches locally on your own server.
