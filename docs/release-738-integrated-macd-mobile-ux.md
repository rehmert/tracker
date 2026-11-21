# Release 738 — One integrated MACD + mobile UX/CSS release

## Objective
Combine the user-authorized system-wide Move/Add/Change/Delete (MACD)
consistency initiative (issue #56) with mobile UX/CSS consolidation
(issue #54) into **one** DEV-qualification and DEV-install release.
No artificial Move actions; Delete and Archive/Stop are deliberately distinct.
This is a single release, not two independently promoted deployments.

## MACD corrections in this release
- Supplements gain an explicit, visible **Delete supplement** alongside Edit
  and Archive, including a confirmation showing related schedules and intakes.
  The original medication-only delete URL remains medication-only.
- A supplement's confirmed permanent deletion reuses the medication's
  all-or-nothing scoped cleanup for intake records, tablet metadata, schedule
  plans and manufacturer facts, with independent audit snapshots and
  wrong-item schedule corruption refusal. No silent related-record loss.
- Regimen schedules gain **Delete schedule**, only when no recorded intake
  references that schedule. If history exists, Delete is not offered and the
  server still rejects forged deletion requests; Stop preserves history.
  Deleting an empty schedule removes its tablet plan and writes audits.
- Intake history gains distinct **Edit intake** and **Delete intake** controls,
  with Edit using its original native form and Delete its existing audited
  signed write route. The delete button is no longer buried in Edit.
- At phone width, the 50-row Regimen intake history is labeled readable cards
  rather than a horizontally scrolling desktop table. Existing desktop table
  and historic intake correction fields remain untouched.
- A module-by-module source-verified MACD capability inventory and
  independent follow-up gaps are recorded in
  docs/tracker-macd-capability-matrix738.md. This is an audit, not a false
  claim that every record supports every operation.

## CSS consolidation — no extra override layer
- The 13 adjacent original Food Journal CSS assets 374–425 have been
  concatenated, **byte-order preserved**, into one
  tracker-food-core738.css. The 13 HTTP stylesheet tags on Food become one.
- The two adjacent Workout action-navigation assets 675 and 696 have been
  concatenated, **byte-order preserved**, into one
  tracker-action-flow738.css in Workouts and Rapid Gym Mode. Their original
  selectors still execute at precisely the same point of the cascade.
- The original source files remain for independently loaded legacy pages,
  historical regression contracts and rollback. Do not delete them until
  source references are inventoried and safely retired in a later release.
- Existing tests that asserted obsolete individual stylesheet URLs have been
  revised to assert the canonical loaded asset **and** that its contents
  preserve the original stylesheet's rules. No behavioral shortcuts.
- No shared global stylesheet selectors were modified. Scoped phone-only
  Regimen card rules were added to the existing Regimen template.

## Single DEV release qualification
- Exact Release 737 DEV and GitHub-main baseline
  0ab7519d9d6b18cce03cc1db59fd9fbbaa1a151b.
- Isolated detached worktree, private disposable SQLite, systemd root worker
  with PrivateNetwork=yes, strict path allowlist and Release 604 static impact
  preflight. Confirm installed DEV remains unmodified after qualification.
- Regression: audited supplement/schedule deletion, rejected attempts,
  cross-linked history, per-record audits, old medication-only 732 flows,
  733–734 UI, 736–737 native disclosure, food history and navigation CSS.
- Real Chromium at 320/390/760/1024, light and dark: native button targets,
  editing expansion, responsive cards and no document overflow.
- Exact concatenation proofs plus browser computed-style parity on both
  action-navigation styles. Preserve Workout finish actions and Food JS.
- Syntax/import, focused backend/API/browser and minimal shared app smoke.
  Not a full app suite; the QA receipt must identify the actual test count.

## Explicit boundaries
- No new migration, dependency, accounts, authentication or CSRF policy.
- No production writes during QA; no secrets, health data, raw logs or
  database backups are committed to GitHub.
- The wider 140-file CSS estate and remaining MACD gaps are inventory
  findings for measured follow-up; never claim all CSS redundancy was
  eliminated by two byte-preserving merges.
- No PROD preflight/deployment without a **separate explicit instruction**
  after passing DEV qualification, guarded installation and hands-on review.
