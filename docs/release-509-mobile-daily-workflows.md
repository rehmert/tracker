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
4. **Distinct installed Android identities.** PWA manifest is served
   dynamically at `/tracker.webmanifest` with `Cache-Control:
   private, no-store`. PROD is Tracker with blue icons and DEV is
   Tracker DEV with amber icons. Both point to `/mobile` as the
   startup page, but each HTTPS origin is a separate installation.
   Existing static icon and manifest paths remain for compatibility,
   although the HTML layout now links the dynamic manifest.
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
