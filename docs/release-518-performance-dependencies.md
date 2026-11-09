# Release 518 — bounded historical marker reads and dependency evidence

Base: Release 517 candidate `9fd83c95fe73f73b9f9b97dd9893e1e38e45f5ff`.

## Source improvements
- Optimize `services.events_between()`: retain dose rows filtered by their
  recorded timestamps; compute lifetime first/last dose times using a grouped
  SQLite subquery; join only vials capable of contributing an in-range marker;
  filter purchase and lab markers in SQL; eager-load compound names.
  Markers retain original timezone and inclusive-window semantics. Date-only
  marker candidates are intentionally filtered a final time by the original
  datetime bounds, to preserve noon event positioning.
- Add regression coverage with synthetic historical and in-range vials,
  administrations, purchases and labs, as well as SQL query-contract checks.
- Add `scripts/tracker-dependency-snapshot.py` to collect **read-only**
  package version evidence and requirements SHA-256 hashes, with an optional
  deterministic comparison against another host's JSON snapshot.
  It never contacts package indexes, installs dependencies, or prints secrets.

## DEV + PROD version capture
On each LXC run (read-only):

```bash
cd /opt/tracker
/opt/tracker/.venv/bin/python scripts/tracker-dependency-snapshot.py \
  --output /tmp/tracker-dependency-snapshot.json
```

Copy the DEV snapshot to a temporary name on the other host (not into the
repository), then use `--compare /path/to/other/snapshot.json` to identify
drift. This is **evidence gathering**, not a lockfile, and no dependency
resolution is changed in this release.

## Separately gated future work
- Health Timeline still constructs full results for unfiltered "All" history.
  True paginated SQL/union filtering with invariant count semantics requires
  large-dataset benchmarks and its own DEV regression matrix.
- The approximately 3,100-line secondary preview module should be split only
  after characterizing route side effects and creating scoped contract tests.
- Dependency lock/constraints must be generated from observed LXC package
  versions, not guessed by source inspection (issue #10).

## Qualification
Do not advance until Releases 515, 516, 517 each pass DEV independently.
Run this exact commit through guarded DEV LXC release tests and inspect
baseline-vs-optimized chart/event equivalence before promoting to PROD.
GitHub is repository only; no Actions or hosted tests.
