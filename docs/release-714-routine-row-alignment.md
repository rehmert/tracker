# Release 714 — Consistent Workout routine editor card alignment

**Pinned installed baseline:** Release 713, `b7253f331ba3d4381328332b3a228148d6fa6d1f`

## Bug

On the saved-routine detail page, the routine exercise cards are laid out
using a wrapping flexbox with `align-items:center`. Short machine names,
for example **Row**, leave sufficient width for substitution controls to
share the line and become vertically centered beside the exercise heading.
Longer machine names wrap the controls to a second row. This produces
inconsistent vertical alignment, as observed for exercise #11.

## Fix

Only `app/static/css/tracker-workouts655.css` and the corresponding
static-asset version in `app/templates/workout_routine_detail655.html`
change at runtime:

- Each routine card uses a one-column CSS grid so the exercise number
  and title **always occupy the first row**.
- The replacement selector and Up, Down, Remove controls start below
  the heading, with the same card-relative vertical alignment for
  short and long exercise names.
- The substitute form is flexible but never wider than its card;
  long exercise names can wrap instead of overflowing horizontally.
- All original POST form actions, button labels, CSRF and data mutations,
  exercise ordering and persistence are unmodified.
- Cache bust the stylesheet to `?v=714` so existing clients actually
  receive the corrected layout.

There are no schema, API, inventory, Workout recording, or dependency changes.

## Qualification

`scripts/tracker-qualify714.sh` runs only on `tracker-dev` as a
PrivateNetwork systemd worker, against a detached exact-SHA candidate
worktree and disposable SQLite database, with a narrowly allowlisted diff.

`scripts/tracker-release-scoped714.sh` executes:
- Browser Chromium checks against the **actual Jinja routine-card markup**
  and actual 654/655 CSS, with synthetic exercise names including
  Triceps Press, Hip Adduction, Row, and Standing Calf Raise.
- Computed rectangle and CSS checks at eight responsive widths
  (320, 375, 390, 430, 600, 768, 1024, 1280 px), proving
  headings are always above actions, controls do not overlap,
  widths remain bounded, four original form actions are retained,
  and the document does not overflow horizontally.
- Existing focused Release 655 routine mutation and ordering tests,
  workout guide contracts, and browser qualification registration checks.
- Bash syntax, Python compilation and Release 604 asset impact preflight.

This is **change-scoped qualification**, not the full application test suite.
Qualified exact-SHA DEV installation uses `scripts/tracker-install714.sh`.
Future PROD promotion requires separate explicit authorization and an
independent PROD scoped rerun through signed DEV-controlled deployment.

Release 714 has no database migration and leaves the installed production
Release 713 unchanged until independently approved.
