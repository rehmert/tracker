# Release 604 — Navigation reduction and fail-fast regression preflight

Base: Release 603 (`ca746febdc037676ca9af9b08fa5cc5ac52a4cfc`).

## UX bundle

### Vials
- Consolidate the two adjacent Vials shortcut bars into a single
  `.tracker-vial-jumps603` navigation.
- Keep all nine destinations: inventory, find, selection, reports,
  lifecycle, add purchased stock, inventory health, alerts and reconciliation.
- The original Vials section-jump script continues opening native report
  disclosures before navigation; selection and inventory controls are unchanged.

### Quick Entry
- Preserve all 15 direct links and the independent searchable action cards.
- Display six daily recording destinations immediately: Today, favorite food,
  water, dose, vital reading and supply use. The six links occupy a horizontally
  swipeable row on phones, preserving Release 602's scroll behavior without
  forcing the entire page wider.
- Group the other nine links under an accessible native **More direct shortcuts**
  disclosure *below* the scrollable row, not clipped inside it. All original URLs
  and hash fragments stay exactly the same.
- Add scoped `tracker-navigation604.css`; do not alter the existing quick-entry
  JavaScript, action filters or forms.
- No persistence, network calls, auto-submission or record writes.

## Fail-fast release gate

New read-only, stdlib-only script:
`scripts/tracker-impact-preflight604.py --base SHA --target SHA`.

The existing guarded deployment script invokes this *inside its isolated
candidate Git worktree* after source parsing and before browser qualification:

1. Require current worktree HEAD to match the pinned target.
2. Determine changed assets and templates relative to the exact base.
3. Reject modifications to JS/CSS still referenced with the old literal
   query-string version from a page template.
4. For changed asset URLs, scan **unchanged** test files for positive
   assertions requiring obsolete version strings. Negative/historical fixtures
   and modified tests are not treated as stale positive contracts.
5. Run the focused Release 604 source, navigation and isolated Chromium
   tests (with a 180-second cap) before the complete browser suite on DEV.
6. Return nonzero with exact paths and reasons before the costly browser and
   backend gates. Does not change the strict-CSRF, qualification, signing,
   backup, rollback or deployment procedures.

The scanner is intentionally conservative: it checks literal script and
stylesheet references and common positive Python assertions. It **does not**
claim to detect every possible stale test or all dynamically constructed URLs.

## Qualification requirements

- Source/regression: `tests/test_release604_preflight.py`.
- Read-only Chromium: `tests/test_release604_navigation_browser.py`,
  covering 320, 390 and 1024 pixel layouts.
- Existing Quick Entry, Vials bulk and navigation, and Release 603 contracts.
- Full guarded DEV Chromium HTTP/HTTPS and complete backend regression must
  pass before signing or promoting Release 604 to PROD.
- No standalone tool or local source check is a substitute for the guarded gate.

## Regression addressed in second DEV qualification

The first Release 604 Chromium pass found two failures in the older Release 602
mobile-density test. The original shortcut bar itself no longer overflowed
horizontally after grouping the links, because the six primary links wrapped.
The corrected `tracker-navigation604.css?v=604b` gives the six-link group its
own horizontal scroll container, leaves the native disclosure visible below,
and preserves two Quick Entry card columns at 390px.

The strict HTTP/HTTPS browser check continues to require **genuine** overflow
(`scrollWidth > clientWidth`) and two columns. It now measures the primary
scroll container rather than the outer navigation node. The isolated Chromium
fixture also loads the Release 602 styling alongside Release 604 and checks
overflow at 320 and 390px. The full DEV gate must still pass before promotion.

## Regression addressed in third DEV qualification

The second DEV run passed the strict browser gate and reached 2,165 backend
passes before the old `tests/test_release_workflow.py` safety contract caught a
second `"$PY" -m pytest` invocation inside `tracker-release.sh`.
That contract intentionally verifies that the canonical full backend suite
remains the **single** pytest command in the deployment script.

The focused regression is now delegated to
`scripts/tracker-focused-regression604.sh` (180-second outer timeout)
without modifying the canonical complete-suite invocation. The helper
also runs `tests/test_release_workflow.py` **before** the expensive browser
suite. `tests/test_release604_preflight.py` checks the helper's presence,
the safety tests, the exact one-command legacy contract, shell syntax, and
the preserved full backend collection.

These are source/test-runner changes only; the application templates and
styling from the corrected mobile layout remain unchanged.
