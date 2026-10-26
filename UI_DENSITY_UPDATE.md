# UI Density Update

Adds a **Display density** control at the bottom of the sidebar, above Appearance.

- **Balanced** (default): reduced padding and section gaps.
- **Compact**: tighter tables, forms, navigation, and dashboard cards.
- **Comfortable**: more generous spacing similar to the previous UI.

The setting is stored locally in the browser (`tracker-density`), applies before the page is rendered, and works with Light/Dark/Auto. No database changes or external dependencies. Existing table no-wrap and horizontal scrolling remain enabled.

## Deploy
Back up your database and uploads; deploy files preserving `.env`, `data/`, and uploads; restart `tracker.service`; hard-refresh the browser.
