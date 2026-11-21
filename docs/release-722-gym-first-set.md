# Release 722 — Gym-floor first-set workflow

**Exact installed baseline:** Release 721 `4983aa242665937f7b851292246b90310b6d50d2`.

## Focused usability change

Put the actively selected machine and its editable weight/reps set form ahead
of secondary tasks on Rapid Gym Mode. The prior recorded set, any frozen
routine goal, and explicit value-copy buttons remain ahead of logging so
they can inform the set. The one-tap **Repeat Last Set** and previous/next
machine links now immediately follow **Save Set**. Load configuration and
offline/draft tools remain available farther down. Planned supersets/circuits
and the existing **Edit Workout Sets** / **Add Machine to Workout** actions
remain available, but no longer precede the primary set form.

An active workout without catalog equipment still offers the in-place
Add Machine controls before the no-equipment message. The new shared
server-rendered Jinja partial prevents two drifting variants of the
add-machine/edit actions. No new JavaScript navigation or automatic writes;
the existing machine selector already auto-advances when changed and still
has a non-JS Go button.

No route, authorization, CSRF, persisted set, routine, set type, rest timer,
goal, correction, deletion, or schema semantics change.

## Acceptance and qualification

- Exact-SHA guarded detached source worktree, private isolated DB,
  PrivateNetwork systemd worker and restricted changed-path allowlist
- Jinja/markup action count, button and workflow order contracts
- Existing rapid-set, correction, delete and completed-edit API tests
- Real signed, disposable 320/390/430px active gym Chromium assertions,
  including inputs preceding secondary tools, no horizontal overflow
- Existing full in-session add/open-machine HTTP+HTTPS Chromium fixture
- Existing accidental/completed Workout delete HTTP+HTTPS Chromium fixture
- Change-scoped tests only; **not** a full application suite

Qualification never installs source. After a passed exact-SHA receipt, the
standard guarded installer may install to DEV for hands-on phone testing.
**Do not promote to PROD without a separate explicit instruction.**
Only after Release 722 is qualified and installed should broader mobile CSS
consolidation (#5) be pursued as a distinct release.
