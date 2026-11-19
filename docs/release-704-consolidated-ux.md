# Release 704 — Consolidated remaining mobile-form usability work

Baseline: verified DEV/PROD Release 703 at
`17e7a68daf8cb9a0c6219b162a54b9e7a1b9f8e2`.
Candidate: `release/704-consolidated-ux-hardening`.

## Release intent

Instead of individual Releases 704–709, this one candidate bundles
the **remaining confirmed mobile form usability corrections** and
requalification of the key earlier improvements. It is a single reviewed
unit with one isolated QA gate, one guarded DEV deployment, and one
DEV-controlled PROD promotion. It does **not** claim every possible
UX/accessibility issue or server performance bottleneck is eliminated.

### Usability changes — three additional long-form workflows

- **Notes editor:** the *original* Save page, Discard local draft and Cancel
  controls become a sticky, phone-friendly action group above the existing
  bottom navigation. The Save action occupies a full-width row at narrow
  widths, with the secondary actions together below. The existing
  local-draft recovery, Visual/Markdown editor, content preview, routes,
  form and draft confirmation are unchanged.
- **Log Previous Workout:** the normal multi-set backdated entry form's
  *original* Save Completed Workout and Cancel become reachable above
  the dock on mobile. The independent **CSV Import** form, add/remove
  set controls, workout date validation, and error/unsaved values are
  unchanged. No new workout or set is recorded until the original
  form is submitted.
- **Manual Lab entry:** the *original* Add row, Save report and Cancel
  controls share a keyboard-aware action region. Add row stays a separate
  HTMX button in the original form, not a submission; its full-width
  row is above Save/Cancel. The separate CSV import form, manual entry
  data and upload, existing duplicate-analyte warnings, completeness
  review and unsaved-change guard are untouched.

All three retain native button/tab order and focus outlines; action
targets are at least 48 px tall on phones <=760px. Sticky behavior
reverts to natural flow while an editing field is focused (the existing
mobile shell also hides its fixed dock). The rules use existing theme
variables and safe-area clearance. Desktop and print remain nonsticky.

The existing Saved Food (702), Vitals and Compound (703), Today, Quick
Entry, Gym Mode and major Inventory/Lab/Food workflow refinements are
**preserved, not reimplemented or riskily replaced**.

### Consolidation decisions

- **One** new scoped stylesheet is shared across Notes, historical Workout
  entry and manual Lab entry, rather than a per-form stylesheet.
- Existing 702/703 styles stay pinned so that their proven behavior and
  historical test contracts remain unchanged; removal/rewrite is **not**
  claimed as part of this release.
- Existing record forms, JS handlers, GET/POST routes, authentication,
  CSRF, SQLite schema, caching semantics, data queries and background
  services do not change. This is not a performance-query optimization.

## Single consolidated qualification

The guarded Release 704 preview requires clean installed DEV `main`
at the exact Release 703 commit, a root systemd worker, active DEV
service, candidate ancestry and an exact nine-file scope allowlist.
It creates **two** detached worktrees (baseline 703 and candidate 704),
each with a separate private empty SQLite data directory, and removes
both afterward. No live data, installed code or PROD state are altered;
no dependencies are downloaded.

- Jinja/CSS parsing and source contracts ensure all three original
  forms' submit, cancel, draft recovery, workout import and Lab dynamic
  row/validation hooks remain unchanged.
- Focused historical tests requalify 702/703 action contracts, previous
  Workout recording safeguards, Vitals dirty guard, Lab duplicate
  handling and copy-from-report restrictions.
- Chromium renders each **real** Jinja editor using representative
  synthetic populated data (one actual workout set, a Lab analyte and
  Notes title). The previous-workout error state is included, plus
  invalid manual Lab date validation. Matrix: 3 editors x five widths
  (320/390/430/760/1024) x 3 density settings x 2 themes =
  **90 presentation configurations**. Assertions check the original
  single Save/Cancel, no horizontal document overflow, sticky clearance
  above the dock, safe keyboard behavior, 44px+ controls, keyboard
  order and one intercepted native Save without HTTP writes.
- Repeat prior Release 702/703 browser tests and historical 603 dock
  pointer/673 integrated-mobile regressions.
- Run unmodified Release 698 **dual-server real-page screenshot** gate
  comparing disposable Release 703 against Release 704 at 10 core
  pages x four viewports x two themes, plus seven anchored sections.
  This is a regression check, not blanket UI approval: a failure
  requires review, never a blanket higher threshold.

No full app suite is requested for this presentation-only release, but
the combined, expanded checks are stronger than any one earlier
single-form release. Record precisely which tests executed. Differences
are retained only in a private DEV review directory on failure.

## Explicit boundaries

- Open **GitHub issue #9**, strict CSRF enforcement, is separately
  gated security work. Do not turn it on in this UX release.
- Open **GitHub issue #10**, locked/reproducible dependency builds,
  requires controlled environment and upgrade validation, separately
  from this release.
- True SQL query performance findings require representative measured
  workloads. There is no responsible claim of performance improvement
  without profiling; Release 704 makes **no** query changes.
- Browser fixtures use synthetic data and do not substitute for
  real-device visual acceptance or exhaustive screen reader audits.

## Release progression

1. Run the root-systemd isolated preview from exact qualified SHA,
   require all source, synthetic browser, dock and screenshot markers.
2. Run the existing guarded `scripts/tracker-release.sh --instance DEV`
   from clean Release 703 DEV at the exact candidate SHA.
3. Visually approve the Notes, previous Workout and manual Lab pages on
   DEV, including edit keyboard and cancel/draft interactions.
4. Run a no-change DEV-controlled promotion preflight against verified
   Release 703 PROD and GitHub main, then use signed `--execute` only
   after approval.

Production changes have **not** been performed by creating the branch
or this document.
