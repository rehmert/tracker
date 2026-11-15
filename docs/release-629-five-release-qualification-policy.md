# Release 629 — Five-release qualification cadence

## Decision

Routine DEV releases now run isolated static checks, source compilation,
Jinja parsing, focused regression tests, backup/restore verification and
post-install runtime health tests. They do **not** rerun the entire
historical Chromium and backend suites after every ordinary UI change.

The complete browser qualification and 16-worker backend regression suite
is mandatory on releases divisible by five: **630, 635, 640, ...**.

Additional complete qualification is mandatory for changes to
`app/routers/`, authentication, CSRF, middleware, scoped database
access or the browser qualification harness, even between milestones.
Unrecognized DEV release naming also fails closed into full testing.
PROD retains the existing full backend qualification and exact-commit
DEV approval requirements until the production promotion process
receives separate review.

The normal focused suite uses 16 xdist workers and the release worker
retains its systemd `MemoryMax=16G` limit. The release is still pinned
to an exact commit; it still uses an isolated candidate, static impact
checks, source and database backup, verified restore, fast-forward
installation, runtime smoke and rollback protections.

## Deployment boundary

This policy is authored on `release/629-five-release-qa-cadence`,
based on the pending Release 628 candidate. It **does not affect the
already running Release 628 systemd worker**: each release copies its
own worker script before starting.

Qualify and install Release 629 only after Release 628 has succeeded
and its exact installed SHA is verified. The next ordinary run is a
focused release; Release 630 is the first regular full milestone.

Known trade-off: regressions not covered by focused tests may first
surface at the next full milestone. The explicit decision to use this
cadence accepts that delay for noncritical issues, not permission
to bypass backup, isolation, approval, or safety checks.
