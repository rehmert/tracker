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
- Routine duplication copies ordered exercises and persistent goals/rest settings,
  never historical sessions or frozen workout targets.
- Future-routine exercise substitution requires cataloged equipment, blocks
  changes during a matching active routine, and clears non-transferable numeric
  goals and old machine-specific setup notes.
- Read-only per-session CSV export of actual logged sets, with formula-safe
  equipment names and existing authentication/database scoping.
- Focused isolated tests for duplication, substitution and CSV safety.
- DEV-driven local deployment script using the signed DEV-to-PROD pathway.
  GitHub is used for Git objects and refs only, never hosted tests/actions.

## Remaining requested scope (NOT IMPLEMENTED / NOT QUALIFIED)

- Workout scheduling and program improvements.
- Advanced Workout analytics.
- Supersets, circuits, exercise substitutions.
- Full workout-session duplication and auditable historical correction workflow.
  (Editable *routine* duplication is implemented.)
- Extended machine/load semantics, and complete Workout CSV import/exports.
  (Session-level actual-sets CSV export is implemented.)
- Offline logging, actionable insights, expanded Workout dashboard widgets.

Do not create `docs/release-668-ready.txt` until **all** bundled features
are implemented, reviewed, tested and a complete qualified migration review
exists for any changed schema. The file must contain exactly:

`RELEASE_668_IMPLEMENTATION_REVIEWED=YES`

The DEV launcher intentionally refuses to deploy without that marker.
This is not a release approval by itself; the exact-SHA guarded DEV
tests, receipt, signed promotion and PROD safeguards remain mandatory.

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
If the final bundled implementation introduces schema changes, the current
launcher fails closed and needs a newly reviewed schema/migration gate and
backup process BEFORE enabling this deployment path.
