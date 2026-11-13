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
  water, dose, vital reading and supply use.
- Group the other nine links under an accessible native **More direct shortcuts**
  disclosure. All original URLs and hash fragments stay exactly the same.
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
5. Return nonzero with exact paths and reasons before the costly browser and
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
