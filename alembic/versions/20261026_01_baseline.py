"""Adopt existing Tracker schemas without discarding data.

Revision ID: 20261026_01
Revises:
"""
from alembic import op
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from app.db import Base
from app import models  # noqa: F401
from app.migrations import migrate

revision = '20261026_01'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    # Reuse the existing, tested idempotent compatibility migrations, using
    # Alembic's connection rather than opening a second writer connection.
    class BoundEngine:
        def begin(self):
            from contextlib import nullcontext
            return nullcontext(connection)
    migrate(BoundEngine())
    Base.metadata.create_all(bind=connection, checkfirst=True)
    # Keep the pre-Alembic marker for compatibility with deployed builds.
    connection.exec_driver_sql('''CREATE TABLE IF NOT EXISTS tracker_schema_migrations
        (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
    connection.exec_driver_sql("INSERT OR IGNORE INTO tracker_schema_migrations(name) VALUES ('tracker_phases_1_3_v2')")


def downgrade():
    raise RuntimeError('Restore a verified database backup instead of downgrading.')
