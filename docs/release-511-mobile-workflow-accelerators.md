# Release 511 — Mobile workflow accelerators

## Scope

This is one bundled, primarily client-side usability release building on
Release 509/510. DEV first, complete regression tests and browser checks,
then promote exactly the validated commit to PROD.

### 1. Read-only recent dose shortcuts

The `/mobile` daily view shows up to five eligible recently recorded doses,
one latest *usable* dose per compound. Each shortcut opens the existing
`/doses?repeat_from=...` **review-only** form. The Dose Log also shows
recent compounds and offers either:

- **Select vial**: selects only the vial; never fills or changes the amount,
  date, injection site, waste type or supplies.
- **Prepare similar**: uses the already-existing historical prefill path. It
  creates a fresh one-use token and asks for explicit review and submission.

The server filters suggestions to real recorded administrations of currently
available vials with enough recorded remaining quantity; waste and discarded
vials are excluded. All queries use `get_scoped_db390`, and read-only GETs
never deduct inventory.

### 2. Searchable vial finder without altering the native select

The normal `<select name="vial_id">` is retained to preserve HTMX previews,
server conversion, inventory enforcement, form validity and browser
accessibility. A client-side search offers up to eight matching choices
by compound, label and vial ID. Clicking one assigns the existing select
and fires standard `input` and `change` events. The browser does not
clone, remove, disable or mutate any real vial options, and Enter inside
the search never submits an administration. Native select remains
available when the search returns nothing.

When coming from a planned calendar entry, the server's existing filtered
vial list is authoritative. Historical shortcuts are hidden for planned
handoffs, so history cannot override compound/date/dose context.

### 3. Today screen improvements

- Compact jump links to vitals, today's doses, upcoming and history.
- **Use current time** in the inline vitals form, using the device's local
  date/time; it changes only the date/time field and never submits.
- More than eight upcoming entries are exposed under an accessible
  **Show more** disclosure instead of silently truncating them.
- Responsive touch targets, keyboard focus indicators and dark/light-mode
  CSS variables via the existing server-managed theme.

### Compatibility and safety

No schema migration, new external library, third-party API, service
worker, PWA manifest update or web authentication change. Developer
tools, CSRF policy, existing idempotency and inventory logic remain
untouched. User content is not written to localStorage or IndexedDB.

## Android acceptance on DEV

1. Open `/mobile` on Android DEV. Verify recent-dose shortcuts are
   distinct per compound and link to an explicit review draft. If
   there are no eligible recorded doses, the shortcut panel is absent.
2. Open `/doses`. Search for a compound and select a vial from the
   results. Confirm that the **original select** and the dose preview
   both update, while amount and time stay unchanged.
3. Choose **Select vial** in Recently used compounds. Confirm only
   vial selection changes. Then open **Prepare similar**, confirm
   historical values are presented for review, and leave without saving.
4. Open a planned item from Calendar. Verify no cross-compound
   historical shortcuts appear and the planned compound remains fixed.
5. On Today, test the jump links, current-time button, and expandable
   seven-day list, if at least nine future items are scheduled.
6. Check desktop and Android layouts, light/dark mode, normal
   dose logging and vitals submission, plus sign-in on DEV.

Only after the successful guarded DEV deployment and mobile acceptance,
promote the exact candidate SHA to `main` for the guarded parallel-test
PROD deployment. No changes should be made to PROD prematurely.

## Test coverage

`tests/test_mobile_workflow511.py` adds nine isolated tests for dose
selection, latest eligible use, deduplication, closed/wasted/insufficient
availability, planned handoff isolation, GET read-only behavior,
time-button semantics, and expected client-side safety invariants.
