#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m alembic -c alembic.ini upgrade head
python -m alembic -c alembic.ini current
