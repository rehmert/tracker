# Release 677 — Recover from Release 676 PROD color-style test failure

The signed Release 676 commit was promoted to GitHub main and qualified on DEV, but
PROD qualification failed on a *serialization-only* assertion:
`rgb(255, 255, 255)` vs `rgba(255, 255, 255, 1)`.
Both represent the same opaque white color. The deployment returned
`PROMOTED_BUT_PROD_NOT_VERIFIED=YES`; this does NOT prove PROD installed 676.

## Split-baseline recovery — fail closed

Expected exact commits:
- GitHub main and DEV installed: approved 676
  `3646f5ebf39f0b0ff2759c35e75df46120a72c7c`
- PROD installed: verified 675
  `2e8f65d7c61c522a5ab01f78cd3783e15559ece3`

`scripts/tracker-release677.sh` explicitly checks these commits before
changing any installation. If PROD did not roll back to 675, STOP and investigate
rather than running this launcher. Its guarded DEV deployment starts from
installed 676; PROD deployment starts from installed 675. Both go to the same
approved 677 target.

`scripts/tracker_promote568.py` preserves signed approvals and the original
guarded promotion flow. Its recovery exception only permits fast-forward over
the exact above 676-main / 675-PROD pair, with ancestry checks, on Release 677.
No force push is permitted; it also checks service and exact DEV qualification
receipts and requires PROD's verification of the signed target.

## Fix

`tests/test_shortcut_buttons_browser676.py` now compares RGB channels of
opaque colors rather than browser-specific CSS color string formatting;
`rgba(..., 1)` and `rgb(...)` must be equivalent.
The runtime CSS, templates, route handlers, forms, data, and CSRF code remain
unchanged.

## Qualification

`scripts/tracker-preview677.sh` performs isolated non-installing tests
on tracker-dev and does NOT promote. The change-scoped Release 677 suite covers
computed mobile styles, existing navigation and Workout regression contracts,
and the exact-base/signed recovery logic. The PROD runner runs **both** the
Release 676 and Release 677 focused suites when installing from 675, catching
color and behavior regressions before touching installed code. The full app
suite is not required for this narrowly scoped recovery.

Never assume PROD is installed from `PROMOTED_BUT_PROD_NOT_VERIFIED=YES`.
Check exact installed commit and service first.
