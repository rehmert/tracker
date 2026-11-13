# Release 602 — consolidated mobile daily workflows

**Base:** Release 601 (`375c17122a67950e5a105f2782bd6cd5df9ff6ed`)

## Combined scope

- **Dose logging:** A four-step mobile guide (vial, amount, time, review) reads
  the existing HTMX form and announces missing inputs. A compact set of up to
  three recent actual administrations links to the existing **Prepare similar**
  GET draft flow. These shortcuts never submit a dose, reuse an old timestamp,
  bypass the final review, or select a potentially unsafe vial automatically.
- **Dose History:** Render existing eight-column history rows as phone cards
  with details disclosure while retaining the same HTMX-owned tbody, edit,
  prepare-similar, and delete controls. No replacement or cloned records.
- **Food Journal:** Automatically expand the reusable-foods section on mobile
  except when following a more specific anchor or saved-food search; make
  food/water shortcuts and common saved-food forms more compact. Existing
  POST forms, serving quantities, and food records stay unchanged.
- **Frontend efficiency:** Precompute reusable-food search labels once and
  coalesce rapid typing events to one animation-frame render.
- **Quick Entry:** Keep every action and direct link but show a short, scrollable
  shortcut bar and compact two-column action cards on suitable phone widths.
- **Accessibility:** Keep >=44px touch controls, focus-visible styles, and
  natural expansion/focus. Respect reduced-motion preferences for Food Journal
  section navigation; ignore malformed hash fragments instead of failing.

## Unchanged safeguards

- Existing server-side CSRF, idempotency and inventory constraints.
- One explicit actual dose submission via the existing /doses form.
- Existing confirmation/read-only review and live vial preview.
- Existing food and vital entry routes and validation.
- Existing desktop table and full-featured desktop pages.
- No database, schema, route, or migration changes.
- No client-side storage of health information.
- Release 600 dropdown scroll restoration remains intact.

## Qualification plan

1. Isolated source/test preflight of Release 602 contracts and existing
   food, dose, daily, navigation, and browser-qualification source tests.
2. Guarded DEV release runs full backend suite plus strict HTTP/HTTPS Chromium.
3. New browser cases exercise responsive dose history, local read-only progress,
   quick food logging, Quick Entry actions and 320px/390px viewport behavior.
4. Manually inspect on a phone: dose shortcuts and final review, a history card
   after a newly logged record, Food quick logging, 320px layout, and
   scroll position on filter dropdowns.
5. Only after approval, signed DEV-controlled promotion to PROD.

## Explicitly deferred

A true single-screen rapid dose POST workflow or standalone food-entry drawer
would duplicate sensitive state and needs separate design/testing. This release
deliberately accelerates existing verified paths instead of bypassing them.
Full Lighthouse and screen-reader audits require live-runtime measurements.
