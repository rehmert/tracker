# Release 678 — Overview Workout Activity: real Daily Shortcuts action cards

**Problem reproduced from user screenshot.** Overview > Workout Activity still
rendered six standard blue, underlined anchor labels inside rounded rectangles.
Releases 675–677 styled `nav.ux675-actions` on Workout subpages, but Overview's
separate `_workout_dashboard661.html` uses `tracker-workout-actions661`, whose
old CSS provided only border, padding and alignment. The old rules never removed
the underlines or set a proper tile layout.

## Correction

- Update `_workout_dashboard661.html`: preserve all six GET destinations, route
  names, accessible labels, and personalized dashboard functionality; use
  explicit shortcut tile class and strong label; give Gym Mode primary emphasis.
- Change empty-state `Log a Previous Workout` into an actual full clickable tile
  rather than an underlined inline link.
- Update `tracker-workout-dashboard661.css` with tightly scoped, high-specificity
  card styling matching Overview's `tracker-daily-flow559-links` pattern:
  border, 9px radius, .75rem padding, clear bold label, no underlines, explicit
  surface and theme colors. Layout 3 columns desktop, 2 on mobile, 1 <=350px.
- Bump stylesheet cache URL to `?v=678` so previously cached CSS cannot mask fix.

## Verification and release discipline

- Actual Jinja Overview fragment is rendered in headless Chromium with a
  simulated *global underlined hyperlink* rule, to ensure the scoped styles win.
- Assert computed no-underline on each of six cards, correct card radius,
  visible backgrounds, >=44px target size, exact routes, responsive layout,
  no horizontal page overflow, and updated empty-state CTA.
- Run existing Release 661 dashboard browser/customization regression and
  focused Release 673, 675 and 676 navigation/style tests.
- Isolated, non-installing DEV preview first; guarded DEV-controlled approval and
  PROD promotion only after preview success. Full app suite not requested.
- No backend, schemas, APIs, CSRF controls or data changes.
