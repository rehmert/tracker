# Release 668 — bundled Workout completion and protocol-calendar order

Release branch: `release/668-workout-completion`.
Baseline: Release 667, `9baa03fb521573ba17ec1853fb85d40a22895336`.

## Implemented and committed so far

- Calendar per-day event ordering by scheduled/recorded local time (HH:MM),
  then case-insensitive compound name, with missing or invalid times after
  timed entries and deterministic tie-breakers.
- Ordinary unmatched single-compound dose logs now carry their recorded
  time into calendar presentation. Reconciled planned entries retain their
  planned time. No logged dose is created, edited, or removed.
- Focused calendar regression tests and a release-scoped DEV QA gate.
- Routine duplication copies ordered exercises, persistent goals/rest settings,
  weekday schedules and groups, never historical sessions or frozen targets.
- Completed workouts can be reused as a new saved routine: only the observed
  machine order is copied, not actual sets or inferred future load targets.
- Future-routine exercise substitution requires cataloged equipment, blocks
  changes during a matching active routine, and clears non-transferable numeric
  goals and old machine-specific setup notes.
- Read-only cross-session Workout Insights: exact 28-day completed-session
  counts, actual sets/repetitions/load × reps, and most recent 12 sessions.
  Empty and unfinished workouts do not count as completed training.
- Read-only per-session CSV export of actual logged sets, with formula-safe
  equipment names and existing authentication/database scoping.
- Focused isolated tests for duplication, substitution and CSV safety.
- Strict future routine-plan CSV import/export (paste-based import), validated
  against the authenticated routine item IDs in one transaction.
- Additive user-scoped weekday routine schedules with optional end dates,
  8-week future preview and explicit remove control. Planned days do not create
  session records or count as completed workouts.
- Local-only set drafts in Rapid Gym with explicit manual restore and later
  online submission; drafts are **not** recorded workouts and never auto-sync.
- Additive named superset/circuit group definitions with 2–10 unique exercises,
  optional rounds, and advisory Rapid Gym navigation. Logging remains manual.
- Audited historical set correction for completed sessions: old/new load,
  repetitions, effort and set type are retained with a mandatory explanation.
- DEV-driven local deployment script using the signed DEV-to-PROD pathway.
  GitHub is used for Git objects and refs only, never hosted tests/actions.

## Deliberate boundaries and remaining verification

- **Offline synchronization:** While the gym page remains open, queued actual
  set entries retry when connectivity returns, and retry-safe server UUID
  receipts prevent duplicate sets. Actions are preserved locally on failures;
  the page does not claim background synchronization after the browser is
  closed. A previously deleted set is never recreated on retry.
- **Historical workout duplication:** A completed workout can be reused as an
  editable future routine without duplicating logged historical performance.
  This deliberately avoids creating false completed training sessions.
- **Supersets and circuits:** Saved groups guide rounds using *actual working
  sets*, excluding warm-ups. They never create sets or silently move/change
  recorded workout data. Scheduling displays planned sessions separately from
  completed workouts on the monthly calendar.
- **Equipment loads:** Store the machine's input mode, multiplier, offset and
  notes. Set weight is exactly the user's entered value; equipment settings
  never retroactively rescale old workout weights or assert that resistance
  across unlike machines is comparable.
- **Analytics:** Provide actual-set 28-day / prior-28-day summaries and per-machine
  observed workloads without simulated strength, subjective readiness or
  automatic load recommendations.
- **Dashboard:** Existing recorded-session counters are retained, with actual
  28-day set and repetition counters and scheduling/insights shortcuts.

Release completion still requires a new exact-SHA DEV preview passing the
expanded focused gates and confirmation of six additive tables, migration
backup and signed promotion safeguards. The preview is **not** deployment
approval. No changes are authorized to authentication, existing historical
schema, dependency versions or deployment topology.

Do not create `docs/release-668-ready.txt` until **all** bundled features
are implemented, reviewed, tested and a complete qualified migration review
exists for any changed schema. The file must contain exactly:

`RELEASE_668_IMPLEMENTATION_REVIEWED=YES`

The DEV launcher intentionally refuses to deploy without that marker.
This is not a release approval by itself; the exact-SHA guarded DEV
tests, receipt, signed promotion and PROD safeguards remain mandatory.

## DEV-only isolated preview qualification (available now)

This runs only the Release 668 scoped tests against the candidate source in an
isolated DEV worktree. It does not install to DEV or deploy PROD. No GitHub
Actions, hosted QA, or other GitHub services are involved.

```bash
sudo bash -c '
  set -Eeuo pipefail
  cd /opt/tracker
  git -c safe.directory=/opt/tracker fetch origin \
    refs/heads/release/668-workout-completion:refs/remotes/origin/release/668-workout-completion
  git -c safe.directory=/opt/tracker show \\
    refs/remotes/origin/release/668-workout-completion:scripts/tracker-preview668.sh \
    | bash -s
'
```

This is a preview test, **not** a DEV deployment receipt. The release
readiness marker is intentionally still absent. It must not be created from
successful preview results alone.

## DEV-only operator command (run as root through sudo)

After release implementation is complete and reviewed:

```bash
sudo bash -c '
  set -Eeuo pipefail
  cd /opt/tracker
  git -c safe.directory=/opt/tracker fetch origin \
    refs/heads/release/668-workout-completion:refs/remotes/origin/release/668-workout-completion
  git -c safe.directory=/opt/tracker show \
    refs/remotes/origin/release/668-workout-completion:scripts/tracker-release668.sh \
    | bash -s -- all
'
```

The script:
1. Confirms `tracker-dev`, local clean `main`, pinned ancestry, completed
   reviewed release marker and unchanged migration/dependency topology.
2. Confirms the installed PROD SHA matches the installed DEV baseline.
3. Executes the exact Git-blob deployment runner in DEV with **no**
   `--full-suite`, allowing the standard isolated scoped tests and safety
   preflight. Checks exact-commit DEV qualification evidence.
4. Uses `scripts/tracker_promote568.py` for preflight, signing, standard
   non-forced Git repository promotion, and SSH-based PROD qualification,
   deployment and verification controlled from DEV.

To stop after DEV, change `all` to `dev`.
To promote an already independently DEV-qualified build, change it to
`promote`.

**No GitHub Actions, CI, or cloud deploy are used.**
The built-in existing runner may still demand a full suite for sensitive
shared-core changes; in that case do not bypass it.
The current branch introduces six additive Workout 668 tables.
The dedicated Release 668 exact-source reviewer and migration/backup runner
are committed. An earlier candidate passed 79 change-scoped tests, but all
new scope must pass a fresh isolated DEV preview before readiness is approved.
The readiness guard remains closed until that qualification and review.
