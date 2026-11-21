# Release 730 — Medication catalog prefill correction + bounded Workout reads

**Qualified DEV base:** Release 729 at `d2597c5bfab3c76e1701a42af00ab5ce41553818`.

## Medication selection bug

Tracker searched RxNorm first, accepting up to eight name-only concepts.
If those filled the result limit, openFDA labels with structured ingredient,
strength and dosage form were never exposed. Selecting a name-only result
therefore often filled only Name, despite an apparently successful lookup.

**Fix:** Search both bounded medication providers, prefer results with
actual ingredient / strength / form fields, and show up to eight merged
matches. Keep RxNorm name-only matches as fallback if detailed labels
are unavailable. Never infer dosage or strength from a name. In Add and
Edit forms, selection populates the four original submitted fields,
clears stale fields from a prior drug selection, and clearly tells the
user when the selected result has no structured details. Original
manual entries and editable fields remain available.

Version the shipped catalog JS asset to invalidate stale browser cache.
No medication intake, schedule or dose is automatically populated.

## Previously prepared Workout page optimization

The Workout equipment page executed one recent-set SELECT per machine and
rescanned all current workout sets per machine. Replace this with a single
`row_number()` window query preserving performed_at-desc/id-desc and
unfinished-session inclusion, plus a linear Counter for active-set counts.
Keep machines with no past sets mapped to None for the existing UI.

## Change-scoped DEV verification

- Exact-SHA source allowlist; pinned base, detached isolated worktree,
  disposable SQLite, PrivateNetwork and impact preflight.
- Medication provider mock tests: 8 RxNorm names cannot hide an openFDA
  full match; unavailable FDA keeps name-only manual fallback.
- Chromium: both native Add and Edit medication forms; search and select
  without submission; submitted POST carries name, ingredient, strength,
  and form; switching to name-only clears stale previous-drug fields.
- Existing regimen catalog, supplement label and regimen POST tests.
- Workout SQL count tests for 1, 5, 40 machines, tie-breaking, current
  workout, and existing Workout route/dashboard regression.
- No full suite; no schema, dependency, auth or write endpoint changes.

## Deployment

This release supersedes the earlier hold on installing 730 ahead of
PROD 729 because the medication bug was explicitly prioritized.
Once exact qualification passes, DEV may install Release 730 using the
normal automated guarded stage. **PROD remains at 727** until separately
authorized; production promotion of 730 then includes Release 729's
mobile Labs entry changes and both changes in 730. Do not attempt to
promote 729 separately once DEV has advanced to 730.
