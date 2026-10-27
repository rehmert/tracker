# Tracker v2.3 — Protocol editor visible fields fix

- New protocols with no saved items now render an editable compound row immediately.
- Add item uses a direct HTMX GET to `/protocols/row`, inserting the returned row into the table without a custom JavaScript listener.
- Removes an accidentally embedded script from the HTML title element.
- Remove buttons use a native click handler and refresh the calculator if HTMX is present.
- Existing protocol rows remain unchanged; no database migration required.
- 129 automated tests passed (`PYTHONPATH=. pytest -q`).

Deploy by updating application files without overwriting `.env`, `data/`, or `backups/`, then restart `tracker.service` and hard-refresh the browser.
