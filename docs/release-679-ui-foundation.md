# Release 679 — Shared UI foundation, first isolated increment

Baseline: Release 678, `b0a40f02837b6221b9d9474bdc74ac6a7c7835b0`.
Branch: `release/679-ui-foundation`.

## Scope

This intentionally small first release establishes opt-in component styles:
`tracker-ui-actions`, `tracker-ui-action` (including primary and disabled
states), `tracker-ui-card`, metric label/value, feedback, and field errors.

The stylesheet is loaded once by the shared shell. Existing templates do not
receive new class names. Existing routes, forms, persistence, navigation,
Workout code, and database schema remain unchanged. The styles use existing
Tracker theme variables, respect narrow phone widths and visible keyboard focus.

## Why incremental

Release 675–678 revealed that similar-looking components can be separate
implementations and that structural tests alone do not prove appearance.
A namespaced layer avoids an uncontrolled cascade reset while establishing
a common contract for later migrations.

## Change-scoped qualification

Run in isolated DEV candidate worktree using the configured Python/Chromium:

```bash
python -m py_compile tests/test_ui_foundation679.py
python -m pytest -q --tb=short --maxfail=1 tests/test_ui_foundation679.py tests/test_shortcut_buttons676.py
```

The browser test renders a disposable HTML fixture at 320, 390, 768 and
1280 pixels in two token palettes. It checks touch height, layout overflow,
surface border, keyboard outline and visible status. This is **not** an
authenticated, real-page visual regression or a screenshot approval.

## Next release, before any broad migration

1. Capture actual authenticated page screenshots on DEV (mobile/desktop,
   light/dark), with a human-approved reference set and a reviewable diff.
2. Migrate **one** high-frequency entry surface to the new classes, then
   verify save/error/focus flows against the real rendered page.
3. Only then migrate more surfaces and remove proven redundant legacy CSS.

## Safety gate

No deploy/promotion script has been introduced for this branch. Do not
promote to production before isolated DEV qualification, authenticated
visual review, exact-commit preflight and the established guarded operator
promotion. No claims of test execution or deployment are made here.

## DEV operator: isolated preview without installation

On `tracker-dev` as root, while `/opt/tracker` remains clean on Release
678 `main`:

```bash
cd /opt/tracker
git -c safe.directory=/opt/tracker fetch origin \
  refs/heads/release/679-ui-foundation:refs/remotes/origin/release/679-ui-foundation
git -c safe.directory=/opt/tracker show \
  refs/remotes/origin/release/679-ui-foundation:scripts/tracker-preview679.sh \
  > /tmp/tracker-preview679.sh
bash /tmp/tracker-preview679.sh
```

This requires the configured DEV Python/Chromium and an accessible GitHub
remote. The preview runner refuses a dirty checkout or an unexpected HEAD.
It creates and removes a temporary isolated worktree and never installs.

The successful output must contain
`RELEASE_679_PREVIEW=PASSED_ISOLATED_NO_INSTALL` and an exact target SHA.
Treat any failure as a block; do not bypass the baseline lease.

## Authenticated real-page review (after separate DEV installation)

`scripts/tracker-visual-capture679.py` offers read-only page navigation for
Overview, Today, Food, Doses, Workouts and Rapid Gym at 390px and 1280px,
requesting light/dark color schemes. It requires an existing private
Playwright `storage_state` file and an HTTPS DEV origin. It will not log in
or write to the application. Its captured images remain in a chmod-700
directory on DEV: they can contain sensitive records. Do not commit, upload,
or distribute these screenshots. The site's persisted theme can override
`color_scheme`; reviewers must verify the actual rendered theme.

Example (fill in the actual DEV host and existing private session):
```bash
/opt/tracker/.venv/bin/python scripts/tracker-visual-capture679.py \
  --base-url https://YOUR-DEV-HOST \
  --storage-state /root/tracker-visual-auth.json \
  --output-dir /root/tracker-visual679
```

These captures do **not** constitute automated visual approval or a
pixel-baseline test. They provide review material only; DEV installation
and PROD promotion remain separate guarded stages.
