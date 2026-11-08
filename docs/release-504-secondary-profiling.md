# Release 504 — Evidence-driven Secondary HTTP test profiling

Release 503 removed an xdist `loadfile` scheduling bottleneck by separating
the longest private-workflow test from the readiness tests. The private
workflow itself still performs real authenticated requests against
disposable SQLite workspaces, including audits, CSRF-protected form submissions, and
cross-account checks. These are valuable security invariants and should
not be skipped or stubbed merely for speed.

## What this diagnostic does

`scripts/tracker-secondary-profile504.py` measures every
`httpx.Client.request` within the selected real Release 440 test, using
HTTP method, path, status and wall time. It also measures each
`subprocess.run` invocation of an `app.worker_*` isolation module,
including all subprocess startup and application work.

It prints slowest HTTP requests, per-route totals, private-worker totals,
and pytest's eight slowest setup/call/teardown durations.

The profile does **not** log cookies, CSRF tokens, form bodies, query
strings, passwords, worker input, response content or headers.
It does **not** alter the request paths, credentials, test assertions,
production gateway, DB files, security checks or worker subprocess
implementation. The real pytest fixture always uses a fresh temporary
data root. The diagnostic refuses to run on PROD or against
`/opt/tracker`.

## Recorded Release 504 baseline (2026-11-08)

The existing diagnostic ran successfully on DEV with unchanged real tests:

| Test | Private subprocess calls | Worker time total | HTTP time total |
| --- | ---: | ---: | ---: |
| Full private workflow | 25 | 25.978 s | 27.453 s |
| Authenticated readiness | 16 | 17.132 s | 17.831 s |

Worker calls account for roughly 94.6% and 96.1% of the measured
HTTP time, respectively. The readiness test invokes
`app.worker_read429` 16 times; the private workflow repeatedly
invokes the supply, supply-use, reconciliation and other isolated
workers. This evidence points to imports / worker execution as the
critical path, not HTTP transport or assertion collection.

The new optional `--import-sample` uses CPython's built-in
`-X importtime` flag for **one subprocess per distinct worker module**,
while preserving the same private-worker command body and runtime
environment. Its import instrumentation is slow by design: interpret
sampled import timings independently from the above baseline.
Captured stderr is parsed inside the profiler; only validated module
names and self/cumulative microsecond timings are reported. Never
print raw stderr because it could contain secrets on unexpected errors.

## Run after checking out a disposable candidate worktree on DEV

    cd /tmp/tracker-backups/qa504.XXXXXXXX/source
    /opt/tracker/.venv/bin/python -u scripts/tracker-secondary-profile504.py \
        --test workflow

Optionally repeat for the slower readiness test:

    /opt/tracker/.venv/bin/python -u scripts/tracker-secondary-profile504.py \
        --test readiness --import-sample

These two profiles identify the critical path. Optimize only after
confirming what dominates the 30-second full workflow:

- If most time is spent in new private worker subprocesses, preserve
  per-request process isolation. Consider only narrowly scoped
  improvements to worker initialization, after validating the real
  security boundary and production behavior.
- If one HTTP route dominates, inspect that route's DB access and
  initialization; avoid caching authenticated workspace identity across
  requests without explicit fail-closed tests.
- If pytest fixture startup dominates, optimize only fixture setup in
  a way that preserves authentic password hashing, separate accounts,
  inactive-workspace identity and full schema migrations.
- If timings are distributed uniformly across all requests, avoid
  deleting test actions and instead retain Release 503 scheduling.

This release adds diagnostics and unit checks only, and changes no
application code, security assertions, deployment settings, or test
collection. It must not be deployed to PROD solely to collect a
DEV-specific performance profile.
