# Stage 2 — Dashboard and navigation redesign

- Responsive collapsible desktop sidebar with browser-local preference, accessible mobile navigation drawer, and Escape-to-close.
- Retains Stage 1 light/dark/auto appearance picker at bottom of sidebar.
- Dashboard hero with quick links to dose and vitals entry, modern metric cards, panels and status badges.
- Client-side search for saved protocols and current vial inventory; no server changes.
- Keeps existing URLs, HTMX forms, PK charts, no-wrap horizontally scrollable tables and all inventory calculations.
- No database migration.

Deploy over your existing application, preserving `.env`, database, `data/`, and uploads. Restart service and hard refresh browser.
