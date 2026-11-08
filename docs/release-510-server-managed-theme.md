# Release 510: persistent server-managed Tracker theme

Installed Android Tracker is a PWA: it already loads the same web styles as
the desktop browser. Release 510 adds one **runtime-editable stylesheet** so
administrators no longer need to modify source code or redeploy for appearance
changes.

## Request path and storage

- On every page, the final global stylesheet is `/ui/theme.css`.
- The backend reads `TRACKER_DATA_DIR/tracker-theme.css` on **each GET**.
- If the override is absent, unreadable, invalid UTF-8, a symlink, or larger
  than 64 KiB, it serves the checked-in default
  `app/static/css/tracker-server-theme-default510.css`.
- The endpoint is protected by Tracker's existing application authentication.
  It does not expose an arbitrary filesystem location or accept POSTs.
- Each response is `text/css` and `Cache-Control: private, no-store`,
  preventing stale CSS in the installed Android PWA. No service worker
  or offline cache is introduced.
- Because the custom stylesheet lives under `TRACKER_DATA_DIR` (outside
  the tracked `app/` tree), guarded releases leave it in place.
- Existing Light, Dark, and Auto modes still work; the CSS defines
  both `:root[data-theme="light"]` and `:root[data-theme="dark"]`.

## Create a persistent editable copy

After the guarded deployment succeeds, determine the actual
`TRACKER_DATA_DIR` used by your systemd `tracker` service (the same
directory containing `tracker.db`). Create the override, e.g. when
`TRACKER_DATA_DIR=/opt/tracker/data`:

```bash
sudo install -m 0644 \
  /opt/tracker/app/static/css/tracker-server-theme-default510.css \
  /opt/tracker/data/tracker-theme.css
```

If the file already exists, **do not overwrite it**; edit that file.

Then adjust `--teal` (legacy token still used by most UI components)
and `--tracker-brand-blue` in the light and dark blocks:

```css
:root, :root[data-theme="light"] {
  --teal: #1265ad;
  --teal-ink: #ffffff;
  --tracker-brand-blue: #1686df;
}
:root[data-theme="dark"] {
  --teal: #79b8f7;
  --teal-ink: #102438;
  --tracker-brand-blue: #65b9ff;
}
```

Edit a local stylesheet file via SSH or configuration management,
then **refresh the desktop page or reopen/refresh the installed PWA**.
There is no rebuild, restart, redeploy, or Android reinstall for CSS
changes. Edits are visible on the next stylesheet GET. The DEV
launcher icon and PROD launcher icon are *installation metadata*,
separate from CSS, and may still require reinstalling to refresh.

## Safety and troubleshooting

CSS is code executed by your browser's styling engine. Only trusted
administrators should edit `tracker-theme.css`. Do not add remote
`@import`, `url()` assets or sensitive information. Keep editing the
file in a private network and do not give public users write access.

```bash
curl -fsSI http://127.0.0.1:8000/ui/theme.css
# If HEAD is unsupported, use:
curl -fsS -D - -o /dev/null http://127.0.0.1:8000/ui/theme.css
```

Expected: HTTP 200 (when authenticated), `content-type: text/css`,
`cache-control: private, no-store`, and
`x-tracker-theme-source: default` or `override`.

A reverse proxy should respect `Cache-Control` and not cache this path.
The existing app's CSRF, login, content isolation, and guarded deployment
checks remain unchanged.

The last stylesheet is global; pages that explicitly define their own
styles may need more-specific override selectors for those elements.
Where possible, use shared CSS variables instead.
