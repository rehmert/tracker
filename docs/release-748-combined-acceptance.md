# Release 748 — Combined #54 mobile, #56 MACD and #10 dependencies

Baseline: Release 747, exact SHA `a0a42cd345f15e61e6a44a20e151271b1ccb0e08`.
Branch: `release/748-mobile-macd-dependency`.

## Shipped into the DEV candidate

### #54 — real mobile controls, not another global CSS cascade

The Notes version-history page had two raw inline text links, unlike Notes' main management page.
They are now semantic `nav` actions using the existing `tracker-integrated-macd741.css`
shared control class, with 44px minimum targets (48px on phone), keyboard focus support,
wrapping, and preserved destinations. A synthetic Chromium DOM/viewport test covers
320, 390, 430, 760, 1024 px and light/dark without any new override stylesheet.
History revision disclosure and confirmed restore form remain intact.

### #56 — end-to-end MACD paths and boundary proofs

Added actual isolated HTTP and HTTPS signed positive/forged/missing CSRF lifecycle
tests for Notes Edit / Restore history, and Labs Add / analyte Add / Edit / Delete,
report date correction (contextual Move), and report Delete. This supplements
Release 747 Notes add/edit/delete, Regimen and Workout signed writes and the
existing multiuser and owner-scoped database regression suites.

No changes to permission, ownership, destructive dependencies, or actual user data.
A **real separate-user** app-wide walkthrough remains an acceptance check, not a
feature to enable or a test that synthetic single-account fixtures can certify.

### #10 — actual browser binary/ELF dependency evidence

Added `scripts/tracker_browser_elf748.py`: inspect the installed Playwright
Chromium binary's `ldd` resolution, hash the resolved regular ELF libraries
(including normal library symlink targets), and write a sanitized no-clobber
private JSON receipt. The qualification runner also performs a **real read-only
DEV-host capture** under a network-isolated worker and deletes the ephemeral
receipt when the worktree is cleaned up. No paths, host credentials, installed
artifact bytes, receipts or medical data are published on GitHub.

For a retained, independently reviewed DEV and PROD comparison, on each host
create a private mode-0700 directory under `/tmp`, run the pinned virtualenv
Python from the installed matching source with `--capture --output /tmp/.../host.json`,
then compare those privately retained receipts with `--compare DEV_JSON PROD_JSON`.
Never copy those host receipts to the code repository.

An ldd map does not establish dlopen/runtime completeness, offline Chromium
replay, externally verified package provenance, or an actual successful OS/browser
rollback. None is inferred or authorized by Release 748. No dependencies were
changed or downloaded.

## DEV acceptance checklist

- [ ] On a real phone, open a Note, use Version history, confirm Back/Edit
  actions have comfortable targets and fit without horizontal scrolling
- [ ] Expand a revision, confirm Restore confirmation and saved history
- [ ] Navigate Workouts on the real phone, including the Edit Workout and
  adjacent Delete action and accidental-session correction
- [ ] Exercise Add/Edit/Move-or-reassign/Delete on relevant user records,
  confirming destructive dependencies are guarded and actual histories remain
- [ ] Using separately authorized QA accounts only, verify another user's data
  cannot be read or edited; avoid enabling the legacy secondary-user cutover
- [ ] Independently capture and compare DEV/PROD private host evidence,
  validate offline browser launch and rollback before calling #10 complete

Do not close #54/#56/#10 based only on synthetic Chromium or route tests.
DEV install requires an exact-SHA passing qualification receipt.
**PROD is explicitly NOT AUTHORIZED in this request**; require user review first.
