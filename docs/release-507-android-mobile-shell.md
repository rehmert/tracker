# Release 507: Android-first Tracker mobile shell

## What ships

Release 507 builds on the existing FastAPI/Jinja/HTMX UI instead of
introducing a second backend or a mobile-only data model.

- Single canonical `/static/tracker.webmanifest` reference in the
  application layout (the previous layout linked two different manifests).
- Installable manifest with stable same-origin scope, standalone display,
  192x192 / 512x512 PNG icons, SVG fallback, and Android launcher shortcuts
  to Quick Entry, Doses and Vitals.
- Thumb-accessible bottom navigation for Home, Today, Add, Doses, Vitals,
  and More, only at 760px or narrower. "More" uses the **existing**
  tested side navigation, not an alternate menu.
- Keyboard-aware hiding, safe-area padding, status highlighting, and
  notifications moved above the dock on mobile.
- No service worker, local cache of Tracker data, background sync,
  new cookies, new permissions or public network exposure.
- Five static regression tests verifying the manifest, PNG binary headers,
  mobile routes and responsive integration.

This is a **mobile installable web app**, not a compiled native APK. An
installed Android PWA launches from the app drawer/home screen without
Chrome address bars, but Chrome still supplies its underlying web engine.
The mobile application stays connected to the same DEV or PROD SQLite
backend, so you do not need a data synchronization system.

## Tailscale and HTTPS: no port forwarding needed

Android browser app installation normally requires HTTPS on a trusted
origin, not merely an encrypted Tailscale WireGuard tunnel. If your
current Tracker URL is a `http://100.x.y.z:PORT/` address, the app will
not be installable as a full standalone PWA from that insecure origin.

Tailscale Serve provides private HTTPS on a node's `*.ts.net` hostname
using MagicDNS and a TLS certificate. It is reachable only inside your
tailnet, so there is no need to open a WAN port.

On `tracker-dev` (after checking that Tailscale is installed on that
node, MagicDNS/HTTPS are enabled, and identifying the actual localhost
port that the running Tracker service listens on):

```bash
tailscale serve status
ss -ltnp | grep -E ':(8000|8080|8443)\b' || true
# Substitute the REAL Tracker upstream port, here 8000 is an example:
sudo tailscale serve --bg 8000
tailscale serve status
```

On `tracker-prod`, use its own real upstream port and its own tailnet
hostname. If Serve is already configured for that node, inspect its
status before changing it, so you do not replace an unrelated proxy.
Do NOT use `tailscale funnel`, which would publish the service.

Use the HTTPS URL printed by `tailscale serve status`. This will look
like `https://tracker-dev.<tailnet-name>.ts.net/`, but do not assume
a hostname until you see the actual output. Distinct DEV and PROD
hosts/origins install as separate apps.

## Android installation

1. Keep Tailscale connected on the Android phone and sign in to the
   tailnet that contains Tracker.
2. Open the actual `https://...ts.net/` PROD URL using Chrome on Android,
   then log into Tracker using the existing account.
3. In Chrome's menu choose **Install app** or **Add to Home screen**,
   depending on device/browser. For a fully installable PWA, Android
   creates a stand-alone launcher entry; if it only offers a shortcut
   that opens Chrome tabs, verify HTTPS, manifest and icon loading.
4. Launch Tracker from the app icon. The fixed bottom bar offers the
   most common day-to-day destinations. Use More for the full sidebar.
5. Optionally install DEV separately, with its own tailnet HTTPS URL,
   to test changes before promoting them.

If Tailscale disconnects, the app cannot reach its backend. This
release deliberately does **not** cache or edit health/inventory data
offline, to avoid stale clinical records or duplicate entries. Check
that the app is usable on both home Wi-Fi and cellular with Tailscale
connected.

## Android APK later, if needed

Once the PWA is confirmed satisfactory on the phone, the next decision
is whether a distributable APK adds value. A Trusted Web Activity (TWA)
made with Bubblewrap can provide an Android package, but requires a
working HTTPS origin and digital-asset-links verification. It still
uses a browser engine and tailnet access. Capacitor/Android WebView
provides a different wrapper with more native integration but demands
additional Android app build/signing maintenance.

Prioritize phone-only features before an APK: a one-screen quick capture
flow, large dose/vital input fields, camera-based vial/barcode scanning,
favorite compounds/vials, and an optional day view. Keep one data model
and one server-side authorization model.

## Acceptance and release

On `tracker-dev`, qualify this candidate in a disposable worktree with
Python compilation, the five new mobile tests, and the complete existing
16-worker backend suite. The existing browser gate and guarded
backup/restore checks still run during DEV deployment. Only promote to
`main` after DEV deployment and on-device Android checks succeed.
No server port configuration changes are introduced by this release.
