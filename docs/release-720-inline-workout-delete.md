# Release 720 — Compact Delete action next to Edit Workout

**DEV baseline:** Release 719, SHA `9fd92b3ac3057af99f8b9e468e27e64bcb2b9e68`.

## Requested UI correction
**Workouts → Recent Workouts** must show a compact **Delete** button immediately beside **Edit Workout** for each completed session. No full-width expandable form, no extra text field, no checkbox. Clicking Delete opens the existing native browser confirmation; Cancel leaves the workout untouched. Confirm sends the existing signed POST to `/workouts/sessions/{id}/delete` with an exact started-at stale guard, confirm flag and a meaningful default audit reason. The existing Release 719 atomic removal and private audit remain unchanged.

Use the same compact action on the active session, in Rapid Gym Mode, session history navigation and review navigation, so users can delete accidentally started sessions. Touch targets are at least 44px and grouped actions remain adjacent on mobile.

The dashboard's collapsed ten-at-a-time Recent Workouts history from Release 719 is unchanged.

## Focused qualification
- Source/Jinja contract checks: compact POST, confirmation, exact session and timestamp, required fields, no disclosures or double-confirmation UI, Edit/Delete adjacency, mobile CSS cache version.
- Existing backend session deletion and audit regression, completed workout review/edit regressions.
- Signed disposable mobile Chromium HTTP+HTTPS: cancel an active-workout deletion, confirm it, create a completed session, verify adjacent **Edit Workout** and **Delete** buttons on its Recent Workouts row, cancel then confirm deletion, and verify it is gone.
- Exact-commit, isolated QA from clean installed DEV Release 719 with no schema migration, no full suite and no live mutation. Only after successful receipt may DEV installation run. No PROD authorization.
