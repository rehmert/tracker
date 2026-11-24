# Release 774 — edit and save Google Tasks titles together

Starting from PROD/DEV Release 773, this code-only release replaces per-row
Google Tasks title Save buttons with a single batch-edit experience. Users can
edit every visible medication/supplement schedule and active protocol item
on `/integrations/google-tasks`, then use **Save all titles** (shown above
and below the list; both controls submit one form and one transaction).

The existing GoogleTasksTitle773 store remains intact: blank title restores
automatic naming, 80-character single-line validation stays enforced, and
short titles affect only projected Google task labels/notes. The 24-hour
prefix, dose schedules, medication data, Google task IDs, completion status,
and sync behavior do not change. Inactive/what-if protocols remain hidden.
Individual Include/Exclude controls remain separate.

All submitted source IDs must match the current visible set; stale or
unexpected/duplicate fields are rejected without changing any titles.
New, changed and cleared titles are committed together only after validation.
No schema, auth, OAuth, network or dependency changes, so no migration required.

DEV-first: isolated change-scoped tests, then guarded DEV installation;
never promote to PROD without separate explicit user authorization.

The enduring design rule is in `docs/ux-batch-editing-guideline.md`.
