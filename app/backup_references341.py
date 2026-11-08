"""Verify that stored SQLite attachment references exist in the archive."""
import sqlite3
from contextlib import closing

_TABLES=(('coas','coa'),('lab_reports','labs'))


def required_attachments(snapshot):
    required=set()
    with closing(sqlite3.connect(snapshot)) as db:
        db.execute('PRAGMA query_only=ON')
        for table,folder in _TABLES:
            exists=db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            ).fetchone()
            if not exists:
                continue

            columns={
                row[1]
                for row in db.execute(f'PRAGMA table_info("{table}")')
            }
            if not {'stored_name','original_name'} <= columns:
                continue

            for stored,original in db.execute(
                f'SELECT stored_name,original_name FROM "{table}"'
            ):
                if not original:
                    continue

                if (
                    not stored
                    or stored in ('.','..')
                    or '/' in stored
                    or '\\' in stored
                ):
                    raise ValueError(
                        f'Unsafe attachment reference in {table}'
                    )

                required.add(f'uploads/{folder}/{stored}')
    return required


def assert_complete(snapshot,archive_entries):
    missing=required_attachments(snapshot)-set(archive_entries)

    if missing:
        raise ValueError(
            f'Backup contains {len(missing)} missing referenced attachment(s)'
        )
