# Release 700 — Shared toolbar and Daily Shortcuts CSS consolidation

Baseline: Release 699, DEV- and PROD-verified
`a49cee23a1c3b87312a603a169be070fbe93faee`.
Candidate branch: `release/700-shared-toolbar-css`.

## Scope and rationale

This is the second narrow visual-preserving CSS consolidation increment.
No user-visible feature, form behavior or database change is intended.

- `app/static/css/tracker-shortcuts-toolbar687.css`: two desktop-sized
  search components (`.workspace-search` and `.workspace-nav-find`)
  already shared identical 761px+ sizing. Factor both into the same
  `:is()` selector in the general desktop rule and the 761–1199px rule,
  preserving specificity, properties, breakpoints and media order.
- `app/static/css/tracker-dashboard-polish688.css`: **unchanged**.
  The isolated preview caught a failed attempt to remove Compact shortcut
  centering: the earlier Release 687 stylesheet uses a more specific
  `align-items:flex-start` rule. The later Compact `align-items:center`
  and `justify-content:center` declarations are required for appearance
  parity and remain intact.
- `app/templates/base.html`: update only the changed Release 687 CSS URL
  to `v=687-css700` so browsers do not reuse cached pre-consolidation
  styles. The unchanged Release 688 CSS retains `v=688`; asset order and
  HTML structure are unchanged.
- `tests/test_shortcuts_toolbar687.py` and
  `tests/test_dashboard_polish688.py`: align only historical asset-key
  assertions with the 687 cache refresh; preserve behavioral assertions.

No other app styles, HTML structure, Python code, JavaScript, schemas,
endpoints, authentication, CSRF, logging or existing records are modified.

## Change-scoped qualification

The release preview compares **pinned Release 699 source** against the
candidate in separate detached worktrees, using separate empty disposable
SQLite data directories and two isolated `127.0.0.1` servers.

1. `scripts/tracker-release-scoped700.sh` runs shell and Python syntax,
   template parsing, new Release 700 source contracts including an explicit
   assertion that Compact centering **must override** Release 687, and
   the existing Release 687/688/689 tests plus Release 690 source guard.
2. `tests/browser/test_css_parity700.py` compares the real
   `app.css`, 685, 686, 687 and, where appropriate, 688/689/Workout/Daily
   CSS in actual Chromium. The static fixture covers toolbar controls,
   both search widgets, section jump, daily shortcut actions and workout
   metrics. It runs across **5 widths (320, 390, 768, 1280, 1920),
   3 densities (Compact/Balanced/Comfortable), 2 themes and 2 style modes
   (687 only, combined): 60 strict comparisons**. Every computed property
   and geometry value must match; every pixel must be identical. Any
   horizontal overflow change also fails. The strict browser harness
   compares baseline and candidate **in the same foreground tab**, first
   requiring the baseline screenshot itself to repeat identically; it
   disables transitions/animations, awaits fonts and paint, and blocks
   all external asset requests. This prevents cross-tab focus paint
   differences from being misclassified as a CSS change.
3. The **existing Release 698 real-page visual gate** runs unchanged after
   the strict CSS tests: 10 real pages, 4 widths, 2 themes and 7 additional
   anchored sections, totaling **136 comparisons** with the previously
   defined small difference threshold and overflow protection.
4. The preview enforces an exact nine-file allowlist and strict baseline
   and candidate SHA verification. It will not install, change main or
   touch production, and makes no network downloads.

All captured content is generated from empty disposable data. The real-page
browser may only load assets from the two loopback servers; the strict
CSS parity browser blocks network requests altogether. Any screenshot
mismatch, including an unstable baseline, leaves locally private baseline,
candidate and diff images for diagnosis. The threshold is **still zero
changed pixels** for strict CSS parity.
Never publish these images without inspection.

The strict parity checks complement, but do not replace, the limited
real-page screenshot matrix; they cannot prove exhaustive accessibility
or all in-session interactions. Browser behavior checks are preserved by
running the focused historical test modules. A cosmetic change intended
in a later release must be explicitly reviewed, not silently accepted by
weakening thresholds.

## Rollout boundary

No claim of executed tests, installed DEV or deployed PROD is made by this
document. First run `scripts/tracker-preview700.sh` in a guarded,
detached systemd worker on `tracker-dev` and require its exact-commit
pass receipt. Only then use the existing DEV release runner, verify
readiness/qualification, conduct a dry-run signed PROD promotion, and
after acceptance, execute the established DEV-controlled deployment.
The full application suite is deliberately not required for this
narrow CSS-only change; report the precise executed test scope.
