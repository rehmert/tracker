# Tracker v2.3 — Protocol compound submission fix

## What changed

- The protocol editor's **Save & add another** button now submits the entered compound rows via a standard HTML POST to `/protocols/{pid}/add-item`.
- The server persists the entered rows and redirects back to the editor with one new blank compound row.
- **Save protocol** now uses a standard POST and redirects to the editor with a confirmation message.
- HTMX remains optional for live what-if calculations, but is no longer required to save or add compounds.
- Existing saved protocol items, units, and schedules are retained.

## Validation

`PYTHONPATH=. python -m pytest -q`: 130 passed.

## Deployment

Back up the application database, update application source files without overwriting `.env`, `data/`, `backups/` or secondary backups, restart `tracker.service`, and hard-refresh the browser. No database migration is required.
