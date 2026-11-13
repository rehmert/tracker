# Release 601: Mobile workflow consolidation

**Base:** Release 600 (`3799113b605c8d1ae9517ddfbd258a527c7e041a`)

## Scope
- Fix accidental double escaping in the global section deep-link JavaScript:
  Unicode mark stripping, title whitespace normalization, and legacy
  `#tracker-section-N` links.
- Prioritize today's actual due/recorded schedule on the mobile Today screen.
  Add a compact glance strip; keep all recorded and due rows unchanged.
- Retain the full seven-day upcoming period on mobile. Show the first eight
  projections, state the full count, and expose every remaining projection
  through an accessible `details` disclosure. Projection never records a dose.
- Re-present the canonical Vials table as compact mobile cards by default
  and allow switching back to the full table, with view preference saved in
  browser-local storage. Card details reveal less common columns on demand.
  All ten columns, row IDs, bulk checkboxes, pagination, sort header controls,
  forms, and database values are unchanged.

## Guardrails
- No route, database, schema, scheduling, or inventory mutation changes.
- No new write behavior or automatic dose logging.
- No cloned/replaced vial rows, preserving page selection and sorting.
- Desktop keeps the original vial table.
- The full table is always available in phone layout with one tap.
- Existing Release 600 dropdown scroll protection remains intact.

## DEV qualification
1. Run the isolated source preflight, including
   `tests/test_release601_mobile_workflows.py`,
   `tests/test_release600_mobile_usability.py`,
   `tests/test_long_page_navigation.py`, and
   `tests/test_mobile_app_shell507.py`.
2. Run the guarded DEV release. The strict browser witness tests in
   `tests/browser/test_strict_csrf521.py` check phone sizes 320/390/430,
   HTTP and HTTPS, the vial-card/table switch, native controls,
   legacy section links, and an accented heading slug.
3. Verify on a physical phone: mobile Today schedule count; expand remaining
   seven-day entries; Vials Card view, More/Less details, Full table, search,
   paging, and bulk checkbox selections; navigating back from a filter.
4. Promote to PROD only after DEV approval using
   `scripts/tracker_promote568.py`.

## Future bundled work
A separate interaction-focused release should consolidate routine dose
confirmation, food/favorites quick logging, shared UI components, and
performance/accessibility instrumentation. Those workflows need deeper
validation than read-only presentation changes.
