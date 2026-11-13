# Release 603 — Inventory, Purchases and Quick Entry consolidation

**Base:** Release 602, `83bf31621467aef08a65770c6978a31c9cd9131d`.

## Scope bundled into one release

1. **Purchase History phone cards.** The existing seven-cell purchase rows can
   display as accessible mobile cards with a *Full sortable table* switch.
   The same DOM rows, links, server-allocated totals, filter state, sorted
   order and CSV export remain authoritative. No row copies and no additional
   inventory write paths. Card/table preference stores only presentation mode.
2. **Search and filters.** Date-range controls and CSV export are available
   inside an advanced-details disclosure; basic search, vendor, item status
   and Reset stay visible. A date-active indicator avoids silently hiding
   applied constraints. Indexed purchase search text avoids recomputing static
   labels for every keystroke.
3. **New order flow.** Vendor, date, order reference and explicit Save remain
   available; shipping, tax, discount, and notes are grouped as optional
   native fields. Fields remain enabled and part of FormData even when the
   disclosure is closed on phones. Desktop opens the disclosure.
4. **Purchase detail vial form.** Retain original vial kit quantity, unit,
   price-basis, price preview and explicit Add vials controls. Group optional
   cap color, label, lot, expiry and notes into a native disclosure on phones.
   Fields are not disabled or automatically populated.
5. **Vials navigation.** Keep existing inventory filters, multi-vial
   selection, bulk editor, warning summaries, reports and lifecycle. Add a
   compact on-page destination strip so phone users can jump directly to
   the inventory table, quick find, bulk operations and reports. Links to
   native details open their target before browser anchor navigation.
6. **Vials mobile bulk controls.** Reflow all existing buttons as compact
   two-column rows on phones. No change to checkbox selection, persisted
   state, bulk-preview validation, or Delete safeguards.
7. **Quick Entry essentials.** Add an optional *Daily* filter covering
   Food, Water, Doses, Vitals and Supplies. The default remains All Actions;
   Record, Review & Plan, keyboard navigation and direct links are preserved.
   Index static action search text once for faster filtering.

## Safeguards

- No changes to routes, databases, schema or backend inventory calculations.
- Original POST endpoints, CSRF middleware, idempotency checks, native forms,
  and server-side validation remain unchanged.
- No new asynchronous saves, automatic purchases or dose recordings.
- Store only optional card/table preference in localStorage.
- Existing desktop full tables and all advanced features are preserved.
- Stable IDs, selection controls, CSV security, price calculations and
  server-rendered data are preserved.

## Qualification

1. Source preflight for Release 603 plus purchase history, purchase item
   editing, quick entry, vial selection, mobile 601/602 contracts.
2. Full guarded DEV release must pass backend and strict HTTP/HTTPS Chromium.
3. Added browser witnesses cover: purchase card/full-table toggle, advanced
   date-filter active marker and reset, native form fields while closed,
   default-open desktop fields, vial report navigation, Daily filter and
   unrestricted search reset.
4. Manually inspect 320/390/430 phone views and desktop; follow purchase
   workflow with a valid test order only in DEV if you choose to test writes.
5. Signed DEV-to-PROD promotion only after full qualification and approval.

## Deferred

- Refactoring the large Vials inline script into multiple shared modules
  would change event ownership and regression risk; it is deferred rather
  than bundled without dedicated integration tests.
- No wholesale removal of sidebar pages or navigation capabilities.

## Fixed-dock pointer safety (added after DEV browser failure)

The two failing HTTP/HTTPS Purchase History toggle cases were a real mobile
interaction defect, not a timing assertion. The Purchase History Reset button
focuses its search input. While the search field has focus, the fixed mobile
dock is hidden. Pointer-down on the card/table toggle blurs search; the dock
previously reappeared before pointer-up and intercepted the click.

Release 603 now defers revealing the mobile dock until the in-flight pointer
sequence finishes. Keyboard focus and editing behavior remain supported.
The shared mobile-dock JavaScript is cache-busted as `?v=603`.

A new *independent Chromium* regression uses actual Tracker JS, a fixed dock,
and a button deliberately located in the dock hit area. It was verified locally
at 320, 390 and 430px: the original implementation failed 3/3; the corrected
implementation passed 3/3, with real pointer clicks and no forced interactions.

Run the targeted regression first on a candidate worktree:
`pytest -q tests/test_mobile_dock_pointer603.py`.
The guarded DEV release still runs the entire HTTP/HTTPS qualification gate.
