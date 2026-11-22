# Release 751: strict CSRF end-to-end DEV activation

DEV baseline Release 750 (2ff72f49449306ea5b11dc9c861d0cac5973131e).
No changed runtime app code, dependencies, migrations or PROD config.

The existing app already has global opt-in strict CSRF for bounded form,
JSON/JS/HTMX and native multipart endpoint dependency. Release 751 adds:
- HTTP and HTTPS synthetic positive/forged root signed-write regression
- Existing unsafe-route negative matrix, multipart and session-account tests
- Full report-only and strict HTTP/HTTPS Chromium suite in PrivateNetwork
- Mandatory full backend and browser regression before DEV install
- Reversible systemd EnvironmentFile override activating strict on DEV only
- Live process-environment inspection, health and denied-unsigned-POST probe

This release does not automatically activate strict CSRF on PROD or
change /etc/tracker.env. If live DEV activation fails, its managed
override is removed and the prior unit configuration restored.

After verified DEV installation:
  sudo bash /opt/tracker/scripts/tracker-csrf-dev751.sh status
Rollback DEV flag only:
  sudo bash /opt/tracker/scripts/tracker-csrf-dev751.sh disable

Manual DEV browser checks remain meaningful for uncommon long/streamed
forms or third-party clients. Do not assume source-only negative assertions
prove every positive path. Strict PROD activation requires separate
explicit approval and its own signed preflight.
