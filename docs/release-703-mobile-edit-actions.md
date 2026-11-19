# Release 703 — Mobile Vitals and Compound edit form actions

Baseline: Release 702, verified DEV and PROD at
`5d4c2c44ad5afc7d7a5ce1ae5396a03aa48d1528`.
Branch: `release/703-mobile-edit-form-actions`.

## User-visible behavior

The **Edit Vital Reading** and **Edit Compound** pages now use the same
one-row, keyboard-aware phone Save/Cancel treatment first introduced for
Saved Food in Release 702.

At phone widths <=760px the **original** Save and Cancel controls
remain inside their own POST form and form one sticky action region above
Tracker's existing bottom mobile dock. They have touch-friendly 48px
minimum targets, theme-compatible backgrounds, visible keyboard focus,
and wrap on narrow phones without overflowing. The row spans the full
width of each existing grid-based editor, preserving natural document
order and the original native submit and link semantics. The row returns
to its original nonsticky document flow when a field receives focus,
because Tracker's mobile shell hides the dock for the software keyboard.
Desktop and print keep the original positioning.

## Vitals-specific behavior preserved

The existing Vitals unsaved-changes guard injects **Restore Original
Values** and a **No Unsaved Changes / Unsaved Changes** live-status
indicator into the same actions parent at runtime. Both remain present,
in DOM order, and use a second two-column row rather than being hidden
or displaced outside the form. Its dirty-check, restore, submit
validation, confirmation before Cancel, beforeunload handling, and
same existing Vitals endpoint are unchanged. The historical Cancel link
retains its `data-vitals-edit-cancel` hook, and its original time-range
parameters `days` and `events` remain intact.

## Compound-specific behavior preserved

The Compound editor keeps its single Save/Cancel pair, unchanged
`/compounds/{id}/edit` POST, and the original `/compounds` Cancel link.
The compound's **default vial unit** remains disabled when existing
vials lock it, with the hidden `primary_unit` fallback submitted
unchanged. Editing values, categories and notes does not gain any
new write path.

## Application scope / test strategy

Changed application paths:
- `app/templates/vitals_edit.html` — one page-scoped CSS reference,
  original actions wrapper given a CSS hook without altering its children;
- `app/templates/compound_edit.html` — one CSS reference and a new
  CSS class on the existing `ux673-action-row`;
- `app/static/css/tracker-mobile-edit-actions703.css` — mobile-only
  styles plus an explicit print reset. No global CSS edits.

The other five files are two scoped test modules, two guarded preview
scripts, and this document. No new JavaScript, database schema, model,
router, authentication, CSRF, migration or record updates.

`scripts/tracker-preview703.sh` runs as a root systemd worker on
`tracker-dev`, requiring clean installed `main` at the exact Release
702 commit and an active DEV service. It verifies candidate ancestry,
a fail-closed eight-file scope, and source diff sanity. An isolated,
detached candidate worktree uses an **empty disposable** data directory
for all focused source/API tests and is destroyed on exit. No installed
DEV or PROD record store is used and no dependencies are downloaded.

Targeted tests cover the Vitals edit dirty/restore guard, edit/create
parity, native time controls, Compound identity and locked-unit
constraints, the historical Save/Cancel control contract and Jinja
syntax. Browser tests render the real two editor Jinja templates with
synthetic values, not a live server or user records. They load the
existing mobile shell and dirty guard JS along with real app/mobile CSS.
The matrix is two forms x five widths (320/390/430/760/1024) x three
densities x two themes = **60 viewports**, plus a locked-unit case.
It checks the one native form, original endpoints and hidden fields,
Save/Cancel keyboard order, 44px+ touch targets, no horizontal overflow,
sticky bar clearance above the dock, temporary static layout while
editing, Vitals dirty status and restoration, and an intercepted Save
event that makes **no HTTP write**. Historical 673 mobile and 603 dock
pointer regressions also run. No full suite for this small
presentation-only change.

An isolated preview passing is **not** a DEV installation or production
approval. Next steps are exact-commit guarded DEV deployment, visual
review, a no-change PROD preflight, and signed DEV-controlled promotion.
