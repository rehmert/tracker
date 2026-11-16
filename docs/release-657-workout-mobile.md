# Release 657 — Faster mobile workout logging and corrections

**DEV baseline:** 06b8be62f5be455df47be87bc5157b41fcac8783
(DEV-qualified Release 656)

**Source branch:** release/657-workout-edit-next-machine

GitHub is used only for source-code storage. No GitHub Actions, PRs or
GitHub-hosted qualification/deployment.

## Features

- While a workout is active, expand any recorded set to correct its logged
  weight, repetitions, or optional effort value.
- A separate removal form requires the user to check an explicit confirmation
  checkbox. The server also demands confirm_delete=yes.
- Corrections retain the existing set ID, machine, original timestamp and
  session relationship. Removal affects only the selected active set.
- Completed sets and sets from unrelated sessions are not modifiable. All
  endpoints enforce authenticated Tracker user DB scoping.
- An active saved routine displays a per-machine set count and the number of
  distinct routine exercises with sets logged today. This is not a completion
  assessment or recommendation.
- A large Next machine link opens the next exercise in the user's saved
  routine, without requiring a new routine start or changing the workout.
- The existing QR camera, repeat-set, routine editing and machine progress
  remain unchanged.

## Schema and deployment policy

- No database table, model, migration, data correction, or backup policy change.
- The established DEV missing-upload policy is preserved; PROD stays strict.
- All write forms use Tracker's existing server authentication, origin guards,
  and CSRF handling. No external dependencies or remote network calls.
- DEV qualification is isolated and release-scoped, including historical
  Workout 654–656 tests and affected release guards; full suite is not required.
- DEV start SHA must exactly equal Release 656 (above). The candidate must be
  a reviewed descendant, pass the release's source allowlist and scoped tests,
  then go through the existing guarded release process.
- The guarded runner preserves source recovery snapshots, restarts Tracker,
  and completes a runtime smoke test. PROD remains untouched.

## Interface verification

Open the DEV Workouts page, start a session, record a set, expand Edit or
remove this set, modify repetitions, and verify the history reflects only
the corrected values. Attempt a removal without checking Confirm and ensure
it is rejected. Confirm removal, then finish the workout. Historical sets
in the finished session remain read-only.

For routines, start a saved routine with at least two machines, log a set
on the first machine, and tap Next machine. Verify the next machine is
opened and the routine set count accurately reflects unique exercises with
at least one actual logged set.
