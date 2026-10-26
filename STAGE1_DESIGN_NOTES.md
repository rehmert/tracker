# Stage 1 — Soft Modern design system

- Light theme by default, with Light / Dark / Auto controls at the bottom of the existing left navigation.
- Choice is stored in browser localStorage (`tracker-theme`); Auto follows OS settings.
- Theme is applied in the document head before rendering to avoid a dark/light flash.
- Existing chart tokens and PK canvas plots follow the selected theme.
- Sans-serif-only typography with optional local Inter/Plus Jakarta Sans font family fallback; no external font downloads.
- Consistent rounded corners, softer cards, form controls, status tags, and focus indicators.
- Existing nowrap tables and horizontal scrolling preserved.
- No database or route changes. Existing purchase editing, calendar, and PK functions preserved.

## Deployment
Back up your data, deploy application files, preserve `.env`, `data/`, and uploaded assets. Restart Tracker and hard-refresh the browser (Ctrl+Shift+R). Theme choice is browser-specific.

## Scope
Stage 1 does **not** replace the navigation with a collapsible sidebar or restructure Overview; those are Stage 2 items.
