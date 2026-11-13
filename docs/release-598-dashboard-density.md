# Release 598 — Compact section explanations and dashboard vial pages

Base: verified Release 597 \`e898c778ba58542f7697acd6c88b850ac623dea0\`.

## Scope

- Shared explanatory notes immediately beneath section headers are clamped
  to one visual line **only when the rendered text actually exceeds one line**.
  A keyboard-accessible More control expands the original complete HTML
  content; Less collapses it again. Original inline links remain intact,
  alerts are excluded, and resize/font loading can re-evaluate wrapping.
- Dashboard **In Stock** vial table shows five entries per page by default.
  Choices: 5, 10, 25, 50, All. Previous/Next and a live result/status label
  show the currently visible count; changing the existing search filter
  resets the page to 1 and paginates only matching vials.
- Both behaviors are client-side presentation changes: underlying inventory
  and persisted filters are unchanged, and no application API, database or
  security configuration is modified.

## Evidence and release safety

Static regressions verify template integration, explanation accessibility,
pagination sizes and filter composition. The existing four-worker isolated
HTTP/HTTPS Chromium gate additionally exercises More/Less and 13 mock
DOM-only inventory rows across page-size changes, navigation, and search.
Mock test rows never write to any SQLite database.

Qualification still requires guarded DEV preflight and full browser/backend
regression, followed by exact-commit production dry run and guarded promotion.
Global strict-CSRF remains report-only. Source witness count is unchanged
from Release 597 (83/144; 61 still unqualified).
