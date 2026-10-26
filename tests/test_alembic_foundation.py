"""Smoke tests for the formal migration baseline."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(tmp_path, *args):
    env = {**os.environ, 'TRACKER_DATA_DIR': str(tmp_path)}
    return subprocess.run([sys.executable, *args], cwd=ROOT, env=env,
                          check=True, capture_output=True, text=True)


def test_alembic_new_database(tmp_path):
    _run(tmp_path, '-m', 'alembic', 'upgrade', 'head')
    result = _run(tmp_path, '-m', 'alembic', 'current')
    assert '20261026_01' in result.stdout


def test_alembic_adopts_legacy_database(tmp_path):
    _run(tmp_path, '-c', 'from app.db import engine, Base; from app import models; '
        'from app.migrations import migrate; Base.metadata.create_all(engine); migrate(engine)')
    _run(tmp_path, '-m', 'alembic', 'upgrade', 'head')
    _run(tmp_path, '-m', 'alembic', 'upgrade', 'head')
    result = _run(tmp_path, '-m', 'alembic', 'current')
    assert '20261026_01' in result.stdout
