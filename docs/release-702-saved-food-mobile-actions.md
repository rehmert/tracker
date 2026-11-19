# Release 702 — Mobile Saved Food form actions

Baseline: Release 701, DEV- and PROD-deployed
`afba8b1f810d777927679cb6feaaa043396f805d`.
Candidate: `release/702-saved-food-mobile-actions`.

## User-facing change

**Edit Saved Food** is intentionally a long form (name, barcode, serving
basis and sixteen nutrient values, followed by a warning about edits
affecting historic entries). On phones <=760px, the one original
**Save Food Changes / Cancel** row now remains reachable near the bottom
of the viewport while scrolling. The row stays above Tracker's fixed
mobile dock, with safe-area space for supported devices and 48px
control targets. The existing **Back to Food Journal** link at the top
gets a matching 44px tappable treatment.

The action row is **not cloned, duplicated or moved outside its form**:
Save remains the same POST submit and Cancel/Back keep their original
Food Journal destination including the requested date and search anchor.
If a field has focus, Tracker already hides the mobile dock to account
for the virtual keyboard; the form's sticky row additionally reverts to
normal flow so it cannot overlay the active input. The original action
row also remains in natural document flow near the form end.

Desktop >760px retains the original non-sticky row and Back link styling.
Print suppresses the sticky effect. All user densities (Compact,
Balanced, Comfortable) and both color schemes use existing theme vars.

## Exact application scope

- `app/templates/food_saved_edit669.html`: add one page-only stylesheet
  tag and CSS classes to the **existing** Back link and Save/Cancel row.
- `app/static/css/tracker-saved-food-actions702.css`: new, fully
  Saved Food-scoped responsive presentation rules.

Five remaining files are release-specific tests, isolated qualification
scripts and this document. There is **no** JS, router, auth, CSRF, model,
migration, schema, transaction, database or food calculation change.
Optimistic-version checks and the legacy Food edit safeguards are
unchanged.

## Qualification and release control

`scripts/tracker-preview702.sh` enforces a clean installed Release 701
`main` on `tracker-dev`, executed by a root systemd worker. It checks
exact branch ancestry and a seven-file scope allowlist before creating
one detached candidate worktree and an empty disposable
`TRACKER_DATA_DIR`, destroyed on exit. It never reads the installed
production or development application database, installs code, pushes
commits or deploys. No dependencies are downloaded.

Focused static/Jinja and app-route tests cover the existing
saved-food edit POST with in-memory SQLite: successful edits, unchanged
history references, invalid values, version-conflict rejection and
existing editor entry points. No full regression suite is run.

Browser tests render the **actual Jinja editor template** using
synthetic Saved Food data and a deliberately minimal isolated shell.
They load the actual mobile layout/dock, existing 673 action styling
and new 702 CSS, plus the existing mobile shell JS. The matrix includes
320/390/430/760px mobile widths and 1024px desktop, three densities
and two themes. Checks cover one original Save and Cancel, no
horizontal overflow, sticky actions above the fixed dock, 44px+
targets, original links, temporary disablement during field editing
and re-enablement after blur, desktop fallback, and an intercepted
Save submit event that never sends an HTTP request. Two historical
browser modules also guard responsive cards and the dock's pointer
blur/tap behavior.

A green isolated preview qualifies the candidate for **guarded DEV
deployment only**. DEV visual approval and signed DEV-controlled PROD
promotion remain separate. These tests are narrower than a full
site-wide browser regression; the complete application suite is
intentionally omitted for a two-file scoped UI change.
