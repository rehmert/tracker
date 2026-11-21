# Release 723 — Consolidate Rapid Gym CSS without changing visual behavior

**Installed DEV baseline:** Release 722, `40088e446b66285aaa07caf40566e4de80864a98`.
**Scope:** two adjacent pairs of Rapid Gym stylesheets. No app-wide legacy
layout refactor, no schema/dependency changes and no application write changes.

## Exact visual-order consolidation

- Merge former `tracker-workouts662.css` into `tracker-workouts659.css`.
  The original tags were separated only by a deferred JS script, not by
  another stylesheet. Load one combined asset with `?v=723`.
- Merge former `tracker-workout-ux673.css` into
  `tracker-workout-gym667.css`. The original CSS tags were adjacent.
  Load one combined asset with `?v=723`.
- Remove the two now-unused CSS source files and their runtime links.
  Update affected source/Chromium tests to use canonical merged CSS.
- Retain historical numbered audit scripts that pin immutable earlier Git
  objects; they do not represent current live imports.
- Preserve the action navigation system, dropdown semantics, mobile dock,
  dynamic JS, rest timer, machine picker, recorded data, 48px primary
  touch controls, and authenticated server-side writes.

The concatenation preserves existing rule bytes in original order.
The only added text is a separating comment. This removes **two loaded
stylesheets** without adding a third override layer.

## Guarded QA

- Git-baseline exact CSS concatenation proof and historical asset references.
- Jinja parsing, signed Workout source and API behavior regressions.
- Chromium screenshot and computed-style parity across widths
  320/390/430/760/1024, light/dark theme and all three density settings;
  checks scroll overflow and primary button height.
- Existing 662/666/667/673 mobile browser suites against merged assets.
- Strict authenticated disposable HTTP and HTTPS machine-add/edit and
  active/completed workout deletion fixtures.
- Exact-commit allowlist, detached worktree and private isolated DB on DEV;
  no full suite (only affected modules).

A passing candidate receipt permits guarded DEV installation. Release 723
does not authorize PROD promotion. Broader shared application styles require
their own separately reviewed release and real-page visual regression gate.
