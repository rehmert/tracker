#!/usr/bin/env bash
# Release 668: signed DEV-controlled promotion wrapper.
# Default is read-only preflight. Explicit --execute is required for PROD.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
PROMOTE="$APP/scripts/tracker_promote568.py"
BASE=9baa03fb521573ba17ec1853fb85d40a22895336
REF=release/668-advanced-workout

[[ "$#" == 1 || "$#" == 2 ]] || {
  echo "Usage: $0 EXACT_40_CHAR_DEV_SHA [--execute]" >&2; exit 2;
}
TARGET="$1"
[[ "$TARGET" =~ ^[a-f0-9]{40}$ ]] || {
  echo "Release 668 promotion requires exact qualified SHA" >&2; exit 2;
}
[[ "$#" == 1 || "$2" == --execute ]] || {
  echo "Only optional --execute is permitted" >&2; exit 2;
}
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || {
  echo "Promotion may run only as root on tracker-dev" >&2; exit 2;
}
[[ -x "$PY" && -f "$PROMOTE" ]] || {
  echo "Existing DEV signed-promotion script missing" >&2; exit 2;
}
ARGS=(
  --release 668
  --target "$TARGET"
  --prod-base "$BASE"
  --ref "$REF"
)
if [[ "$#" == 2 ]]; then
  "$PY" "$PROMOTE" "${ARGS[@]}" --execute
else
  "$PY" "$PROMOTE" "${ARGS[@]}"
fi
