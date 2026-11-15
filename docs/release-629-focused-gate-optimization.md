# Release 629 — lean routine qualification

## Source and intent

Based exactly on the successfully installed DEV Release 628:
`ad80ae2d2a46be1fbb977347606f98fd76e0f2da`.

Release 628 already installed the five-release full-regression cadence.
Release 629 **only narrows the routine focused test list** to avoid
repeating the entire historical CSRF/source-witness investigation for
ordinary UI and tooling releases.

The existing focused script previously referenced 38 test modules.
It now references 20, including its own scope regression, covering
the release CLI, impact preflight, PK Simulator UX and read-only
source contract, runtime/deployment safeguards and representative
current workflow regressions. The old CSRF witness and runner
historical-compatibility modules are removed from the focused list,
**not removed from the repository**.

Full comprehensive browser/backend regression still runs at
releases divisible by five (630, 635, 640, ...) or where the installed
release policy detects security-sensitive application changes.
PROD approval and its qualification rules are unchanged.

The release worker remains capped at `MemoryMax=16G` and uses
pytest-xdist with `-n 16 --dist=loadfile`. Source checks,
compilation, Jinja parsing, static impact, a verified backup and
restore, pinned commit installation, runtime smoke, live SSH
output, and rollback controls are unchanged.

## Source verification

The mandatory `tests/test_release629_focused_gate.py` guards
the focused list, absence of historical CSRF suites, existing
milestone and security exception paths, worker/memory constraints
and shell syntax. Runtime qualification must still occur on the
disposable DEV candidate before this release can be considered
installed.

No application source or database schema changes are included.
DEV may run the guarded release directly from installed Release 628,
provided the working tree is clean and its HEAD matches the pinned
base SHA. Do not promote PROD as part of this release.
