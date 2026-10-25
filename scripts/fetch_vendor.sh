#!/usr/bin/env sh
# Downloads htmx once so the app has no runtime dependency on a CDN.
set -eu
cd "$(dirname "$0")/.."
mkdir -p app/static/vendor
curl -fsSL https://cdn.jsdelivr.net/npm/htmx.org@2.0.4/dist/htmx.min.js -o app/static/vendor/htmx.min.js
echo "htmx saved to app/static/vendor/htmx.min.js"
