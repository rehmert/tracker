# Release 626 — Phase 2 reproducibility evidence bundle

Starting exact baseline: Release 625 commit
`0887577e61360d2019d9fc5e2bae77847e726d80`.

## Status and scope

This source-only bundle supplies an audited, read-only DEV-vs-PROD comparison
of `pip list --format=json` snapshots with the earlier observed Python 3.13
baseline and its informational candidate constraints. It does **not** pin or
upgrade live environments, nor claim reproducible fresh builds.

The actual installed Python, SQLite, browser and system library versions
must still be collected and independently compared. The 2026-11-11 historical
manifest is an observation, not a current host measurement.

## Host evidence collection (operator action, separate on both instances)

On each host, run read-only commands using the installed Tracker venv:

```sh
/opt/tracker/.venv/bin/python -m pip list --format=json
/opt/tracker/.venv/bin/python -m pip check
/opt/tracker/.venv/bin/python --version
/opt/tracker/.venv/bin/python -c 'import sqlite3; print(sqlite3.sqlite_version)'
/opt/tracker/.venv/bin/python -m playwright --version
```

Save **only** the pip list JSON on a trusted workstation as `dev.json` and
`prod.json`. Never paste or collect `pip config`, environmental secrets,
private registry URLs, `pip debug`, or a complete service environment.
The command below reads local JSON and emits deterministic sanitized diffs:

```sh
/opt/tracker/.venv/bin/python /opt/tracker/scripts/tracker_dependency_host_compare626.py \
  --dev /path/to/dev.json --prod /path/to/prod.json
```

Exit 0 means matching inventories and historical pins; exit 2 means drift;
exit 1 means malformed evidence. This is **not** proof of package security,
deterministic wheel resolution or a clean build.

## Required disposable fresh-environment acceptance (not performed by this release)

1. Provision a separate disposable Python 3.13.5 environment on a clean
   matching OS/architecture with an isolated database and no production
   environment variables.
2. Record exact package and system dependencies including pip, SQLite,
   Playwright Chromium version and browser system libraries.
3. Before installing, check resolved dependency metadata, wheel availability,
   vulnerability advisories and any provenance/hashes. Validate the observed
   candidate pins against requirements; do not treat the historical candidate
   file as a maintained, hash-locked lock.
4. Separately approve installation using a reviewed version lock with
   hashes where appropriate. Run `pip check`, offline source validation,
   all backend tests and HTTP/HTTPS isolated Chromium browser tests.
5. Archive the approved constraints/lock, interpreter/browser metadata,
   package hashes, install logs without credentials and passing test receipts.
6. Test rebuilding and reverting to the previously accepted lock from a
   disposable snapshot, with source and database restore expectations.
7. Establish a scheduled dependency advisory review and updates through a
   **separately reviewed deployment path**, not the guarded source-only
   release mechanism.

A reviewer must explicitly sign off on these results before closing
GitHub issue #10. No silent updates to requirements or installed packages
are allowed in this release.

## Existing safety controls

The interactive guarded DEV deployer, 16 workers, 16 GB memory limit,
HTTP/HTTPS Chromium qualification, immutable DEV receipts, exact-commit
promotion, and independent PROD approval are unchanged. Strict-CSRF
activation remains a separate security issue (#9).
