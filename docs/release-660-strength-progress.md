# Release 660 — Strength Progress Analytics

**DEV baseline:** Release 659,
`a02b70bb085533ff4ec23bae5e2bde9b25e40360`.

**Branch:** `release/660-strength-progress-analytics`.

## Features

Adds a fully server-rendered, read-only **Strength Progress** screen
(`GET /workouts/analytics`). Available from the main Workouts screen,
Rapid Gym Mode, and individual machine progress.

Select an existing machine, or default to the machine from the most recent
*completed* session with a logged set. The chosen machine never silently
changes when the user provides an invalid machine ID (404).

For that **one machine**, show:

- All-time number of completed sessions with sets, recorded sets,
  repetitions, and volume as the sum of logged weight (lb) × repetitions.
- Recorded personal records: heaviest actual set weight and greatest
  actual single-set weight×repetitions, with links to the source workout.
- A chart and table of total volume for up to 20 recent completed
  sessions, ordered by the workout's **original started_at**, including
  manually backdated workouts from Release 658.
- An exact-rep selector: choose among 12 most frequent repetition counts
  and view actual heaviest logged weight at **exactly** that repetition
  count, by completed session. Chart and table again use 20 sessions.
- An empty-state message for machines with no completed sets and for
  valid requested rep targets with no matching sets.

Numeric SVG coordinates are generated solely from server-validated
numbers; machine names and other text are Jinja-escaped. Charts have
text alternatives through the corresponding table and accessible labels.

## Interpretation

- **No 1-rep maximum predictions**, no inference about total muscular
  work, no suggestions for training load or exercise frequency.
- All data come from actual recorded sets in **completed sessions**.
  A still-open session is excluded, even if sets were logged into it.
- No comparisons between machines: mechanical leverage, stack weight,
  machine model and free-weight handling may differ.
- Volume is a mathematical **sum of recorded lb × reps**, not pounds
  lifted as mass over time. Bodyweight work entered as 0 added pounds
  contributes 0, even when the exercise was demanding.
- Exactly matching repetition counts are a more conservative basis for
  comparing recorded load than mixing a 5-rep set and a 12-rep set;
  different range of motion and technique remain untracked.
- An increase is displayed as historical data, not automatically
  judged as an improvement in physical capacity.

## Scope and deployment

- Uses the existing authenticated `get_scoped_db390` and original
  `WorkoutEquipment654`, `WorkoutSession654`, `WorkoutSet654`
  tables. No new tables or columns, migrations, dependency changes,
  service/backup changes, data corrections, or write endpoints.
- Read operations are bounded: all-time aggregates computed in SQL,
  charts and tables limited to 20 sessions, rep selector limited to 12.
- Existing Workout screen, machine-history and Rapid Gym Mode pages
  gain one link each, without altering their original forms or endpoints.
- The exact-SHA source reviewer ensures the above and rejects any
  unreviewed files, changes to the core application outside of one
  router include, or additional changes to existing template layouts.
- Focused tests validate arithmetic, chronological backfilled sessions,
  exact-rep segregation, exclusions for unfinished sessions and
  unrelated machines, empty data, escaping, invalid IDs and no writes.
- Historic Workout 654–659 tests and the existing mobile browser test
  remain in scoped qualification.
- The guarded Release 660 wrapper must run on `tracker-dev` with the
  exact commit. PROD remains on 659 until DEV evidence and a separate
  existing DEV-controlled signed promotion are verified.
- GitHub is version control only: no GitHub Actions and no GitHub-hosted
  testing or deployment.

## Verification on DEV

Open Workouts → Strength Progress. Pick a machine with completed sets,
inspect actual PRs, select a common exact rep count, and verify dates and
loads against normal session history. Verify that active workouts do not
alter these completed-session figures until finished. No new data should
be written by viewing analytics. Exercise names should remain isolated
to the selected machine.
