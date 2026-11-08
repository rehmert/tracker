# Release 509 — Daily Mobile Workflows

## Purpose

Ship a meaningful Android-first UI bundle using the existing FastAPI,
HTMX/Jinja and SQLite application. No new database tables, native
application build, separate API, third-party dependencies or public ports.

## Features

1. **A real mobile Today screen** at `/mobile`. It shows latest
   weight/BP/pulse, today's projected versus actually recorded
   administrations, a seven-day upcoming list, recent dose history,
   and recent vital readings. The server reuses the same
   `schedule_summary` and projection-exclusion logic as Dashboard.
   All DB access uses `get_scoped_db390`.
2. **Quick vitals capture without switching pages.**
   A single responsive form supports Weight, Blood Pressure, Pulse
   and All modes. It posts to the existing validated `/vitals`
   endpoint. The only backend change is an allowlisted
   `return_to=mobile` hint, redirecting success and validation
   errors back to the Today screen. Arbitrary redirect URLs are
   ignored.
3. **Prepare Similar** for recent doses; the shortcut uses the
   existing `/doses?repeat_from=<id>` handler. That handler
   generates a new submission token and requires confirmation,
   checking the current vial's remaining quantity. The mobile
   Today screen never saves a dose.
4. **Distinct installed Android identities.** PROD links to the
   public static `/static/tracker.webmanifest` and DEV to
   `/static/tracker-dev.webmanifest`. PROD is Tracker with blue
   icons and DEV is Tracker DEV with amber icons. Both point to
   `/mobile` as the startup page and install separately by HTTPS
   origin. Only installation metadata and icons are public; all
   health records remain behind the normal Tracker authentication.
   The static path is essential because Chrome cannot reliably
   install from the earlier authenticated dynamic manifest route.
5. **Updated mobile navigation and Quick Entry.** The bottom Today
   tab launches the new page, and Today is included in the existing
   sidebar navigation. Quick Entry offers direct links to Today
   and its quick vital form.

## Existing safety and data behavior preserved

- No offline caching, service worker, request sync or duplicate
  browser-side database. All clinical/inventory records remain on
  the server and use the existing account-scoped storage.
- Scheduled administrations are display-only, with clear status.
  No schedule-to-log auto-writing.
- Vitals are created via the existing `metrics.validate`,
  `metrics.weight_to_kg` and database transaction.
- JavaScript never caches sensitive data in Local Storage or
  IndexedDB. Form mode changes never silently hide entered readings.
  The save button is disabled only after a valid submission starts,
  and is restored when browser navigation restores a page.
- The original guards, release deployment tooling, browser
  qualification, backups and rollback remain unchanged.

## Acceptance (Android Chrome PWA)

- On DEV, open `https://tracker-dev.rehmert.net/mobile` through
  Tailscale with a logged-in account. Verify Today's dock shortcut,
  latest readings, schedules, and recent dose list.
- Record a **test** weight, BP and pulse via the Today quick form,
  one at a time and in All mode. Check that each save returns to
  `/mobile`, and records can be viewed in `/vitals`. Remove
  disposable DEV test records afterward using the existing UI.
- Open Prepare Similar for an actual dose and confirm it prefills
  a new form **without recording a dose**; do not save unless you
  intend to create a DEV record.
- Install (or reinstall to refresh) DEV; its launcher/icon should
  say Tracker DEV and have an amber visual identity. PROD's
  launcher remains Tracker in blue. Depending on Android's cached
  installation metadata, previously installed apps may need
  uninstalling and reinstalling for their names/icons to update.
- Test Tailscale LAN and cellular access, Android back navigation,
  touch/keyboard behavior and the More sidebar.

## Release flow

Apply this **single** candidate via the pinned guarded DEV
deployment, which runs real browser qualification, the complete
backend suite, recovery verification and runtime smoke checks.
After mobile acceptance, promote its exact SHA to GitHub `main`
and perform guarded PROD deployment. PROD now has bounded
parallel backend testing from Release 508.

Expected new tests: 9 in `tests/test_mobile_daily509.py`,
plus the updated Release 507 manifest/dock contracts.

## Deferred

- Native APK: revisit only if deep-link integration, device-level
  notifications or camera capabilities require it. The installed
  PWA already works through private HTTPS and Tailscale.
- Barcode capture and offline editing: keep separate until
  requirements and safe behavior are worked out.

## DEV installation recovery after initial Release 509 rollout

Initial Release 509 linked `/tracker.webmanifest`, an application
route subject to `require_auth`. Chrome on Android can reject PWA
installation when it receives the login redirect rather than the
installation manifest. The in-branch follow-up restores the known
working Release 507 static-hosting approach, with separate public
DEV and PROD manifests and a versioned HTML manifest link.

Validate after guarded DEV deployment:

```bash
curl -k -sS -o /dev/null -w '%{http_code} %{content_type}\n' \
  https://tracker-dev.rehmert.net/static/tracker-dev.webmanifest
curl -sS http://127.0.0.1:8000/static/tracker-dev.webmanifest \
  | python3 -m json.tool
```

The first request should return 200 (certificate trust is
best checked separately without `-k`), and the second must show
`"name": "Tracker DEV"`, `"start_url": "/mobile"`, and both
valid static PNG icons. On Android, reload the logged-in `/mobile`
page, then use Chrome's Install app option. If Chrome caches the
previous failure, close the tab and reopen it after deployment.
Do not expose the private application or open WAN firewall ports.

## Blue accent polish

The user confirmed Android installation works and requested the in-app
accent change from green/teal to blue. The application continues to
reuse the established CSS custom property `--teal` for compatibility,
but Release 509 now sets it to `#1265ad` with white ink in light
mode and `#79b8f7` with dark ink in dark mode. This changes active
navigation, links, primary action buttons, focus accents and mobile
Today measurement tabs consistently. Both color pairs exceed 4.5:1
contrast for normal text. The main stylesheet query version is bumped
to `509-blue-accent` so installed Android PWAs request the new CSS.

The DEV launcher and DEV environment label remain distinct and amber;
the user requested an in-app blue accent in place of green, not the
removal of DEV/PROD environment identification. No schema, dose/vital
write logic, manifest or app dependencies were changed for this polish.
