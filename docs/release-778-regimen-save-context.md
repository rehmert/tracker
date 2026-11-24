# Release 778 — stay with the edited regimen form

The Supplements & Medications page previously returned to the top after a
POST because its post/redirect/get responses navigated to bare `/regimen`.
This was especially disruptive for edit controls well below the fold.

The fix keeps the existing single-page workflow. After schedule or catalog
edits, the server redirects with a validated `focus` query parameter and
matching fragment (for example,
`/regimen?focus=schedule-42&msg=Schedule%20updated.#reg635-schedule-42`).
The browser scrolls to that card; Jinja renders only its edit disclosure open,
so the user sees saved values and can continue without searching again.
It also works without JavaScript, on mobile, and after normal page reload.

- Schedule create: navigate to the newly created schedule's open editor.
- Schedule edit: stay at that exact schedule on success or validation error.
- Schedule stop: stay on the stopped schedule; delete: return to schedules.
- Catalog create/edit: navigate to the matching item's open editor.
- Invalid add-item/add-schedule: return to the appropriate open add form.
- Other flows, saved data, entries, schemas, dose calculations, audits, and
  CSRF protections are unchanged.

The fragment is added after the existing flash message URL encoding, never
before it. Focus destinations are generated from record IDs and an explicit
allowlist, so they cannot introduce arbitrary external redirects or query
parameters. A small scroll-margin avoids positioning the card under a sticky
header. Full-page PRG prevents re-submission on refresh.

Targeted HTTP/SQLite/Jinja regression tests cover supplements/medications,
successful and failed saves, catalog creation, stop/delete behavior, date and
message preservation, allowlisted redirect targets, and existing regimen
tests. No full suite required. Qualify/install DEV first; PROD requires
separate user approval.
