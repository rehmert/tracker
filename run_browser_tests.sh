#!/usr/bin/env bash
# Compatibility entry point. Browser tests require an isolated candidate.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
exec bash "$ROOT/scripts/tracker-test-gate475.sh" browser
