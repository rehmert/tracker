# Release 762 — Comprehensive Body Composition Progress Dashboard

Base: 04fd141daa17fd2055f9177527296eb9165a59d2 (Release 761)
Branch: release/762-body-composition-progress

## Existing data reused

- Weight, resting pulse, systolic and diastolic BP: vital_readings (no copies).
- Lab results and report dates: lab_results / lab_reports (native unit-aware series).
- Completed workout sessions, sets, equipment and working-set annotations:
  workout_sessions654 / workout_sets654 / workout_equipment654 / workout_set_types667.
  Matched comparisons require same equipment ID and exact repetition count.
- Food days and protein targets: existing authorized food journal SQL engine, with
  independently computed nutrient coverage. Absent food records are unknown.
- Existing dose and medication logs remain linked from Health Timeline, and manual
  dated markers can overlay weight/waist graphs.

## Additive, optional model

New progress_settings762, progress_measurements762, progress_composition762,
progress_function762 and progress_markers762 tables. No existing columns change.
Rows belong exclusively to the authenticated Tracker workspace database.
The ORM creates missing additive tables at app startup; existing data is untouched.
No content from any user-specific record belongs in GitHub.

The progress page supports measurements in inches or centimeters, separately
identified BIA/DEXA/manual estimates, joint function, date annotations and a
configurable due checklist. Users can add/edit/delete and backdate records.
Progress-photo *dates* are tracked, not images. Import of actual images and
BIA vendor APIs is deliberately not included; manual entry is supported.

## Interpretation rules

- Scale averages: one most recent actual reading per day. 7d/28d summaries
  show sample counts; comparative change needs >=3/7 logged days in both
  adjacent windows. Sparse readings never imply smooth loss.
- Plateau: four consecutive weekly blocks with >=3 days of observations,
  with earliest/latest weekly means varying by <0.5% of latest mass.
- Body-fat, fat-free mass and visceral fat values are labelled estimates; no
  simulated muscle gain, no cross-method BIA/DEXA stitching.
- Waist-to-height ratio requires a measured navel waist and user-set height.
- Strength improvement compares only the same exercise equipment and exact
  rep count; warmups and incomplete workouts are excluded.
- Reported protein per kg uses latest weight explicitly; incomplete or absent
  nutrient reports never silently count as zero. No clinical recommendations.
- Dated events are context markers only, not proof of intervention effects.
- No composite health score or guaranteed weight forecast.

## Data safety and migrations

The new ORM tables are additive and the default app startup creates missing
tables. The new guarded DEV install performs an explicit, private, verified
pre-install database snapshot before invoking the existing pinned release
runner. No schema backfill or mutation runs during qualification. DEV
qualification runs in a disposable worktree/data directory. The independent
PROD preflight/deployment stage must preserve the established backup and
rollback requirements; it is NOT authorized as part of this release request.

## Scoped qualification

- Syntax/import + HTML/Jinja checks on changed Python/templates.
- Isolated synthetic TestClient and pure-helper tests for CRUD, unit conversion,
  BIA/DEXA provenance, sample coverage, machine matching, nutrient completeness.
- Chromium 360/390/430px offline mobile disclosure and overflow smoke.
- Targeted existing vitals, workout analytics, health insights and dashboard
  regression tests.
- Release 604 static impact preflight.
- No full regression suite or package downloads planned; deployment agent
  requires immutable qualification and DEV install receipts.

## Developer notes

To avoid an unnecessary daily data-entry burden, only waist and other new
measurement forms are editable here. Existing weight, nutrition, workout and
labs are linked back to their established editor screens. The checklist is
informational only (not a push-notification scheduler).
