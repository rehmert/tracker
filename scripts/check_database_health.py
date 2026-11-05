#!/usr/bin/env python3
"""Read-only SQLite health checks, administrator-scoped by default.

Use --scan-all only for deliberate legacy diagnostics. It is not an
account-isolation guarantee.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path('/opt/tracker')

SEARCH_PATHS = [
    ROOT / 'data',
    ROOT / 'backups',
    Path('/tracker-backups'),
]


def check_database(path):
    print(f'\nChecking: {path}')

    try:
        uri = f'{Path(path).resolve().as_uri()}?mode=ro'

        with sqlite3.connect(uri, uri=True, timeout=10) as db:
            integrity = db.execute(
                'PRAGMA integrity_check'
            ).fetchall()

            foreign_keys = db.execute(
                'PRAGMA foreign_key_check'
            ).fetchall()

            print(
                'Integrity:',
                'OK' if integrity == [('ok',)] else integrity,
            )

            print(
                'Foreign keys:',
                'OK' if not foreign_keys else
                f'{len(foreign_keys)} violations',
            )

            return (
                integrity == [('ok',)]
                and not foreign_keys
            )

    except Exception as exc:
        print('ERROR:', exc)
        return False


def administrator_database():
    # Support direct script execution, including Python -I.
    project = str(Path(__file__).resolve().parents[1])

    if project not in sys.path:
        sys.path.insert(0, project)

    from app.background_storage410 import (
        administrator_context410,
    )

    return administrator_context410().database


def discover_legacy_databases():
    databases = []

    for directory in SEARCH_PATHS:
        if not directory.is_dir():
            continue

        databases.extend(directory.rglob('*.db'))
        databases.extend(directory.rglob('*.sqlite'))
        databases.extend(directory.rglob('*.sqlite3'))

    return sorted(set(databases))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
    )

    choice = parser.add_mutually_exclusive_group()

    choice.add_argument(
        '--scan-all',
        action='store_true',
        help='Explicit broad legacy scan; not account-scoped',
    )

    choice.add_argument(
        '--context-check',
        action='store_true',
        help='Validate administrator configuration without opening SQLite',
    )

    args = parser.parse_args(argv)

    if args.scan_all:
        print(
            'WARNING: --scan-all searches legacy paths; not account-scoped',
            file=sys.stderr,
        )
        databases = discover_legacy_databases()

    else:
        try:
            database = administrator_database()
        except (OSError, ValueError, TypeError) as exc:
            print(
                f'FAIL: Administrator database context: {exc}',
                file=sys.stderr,
            )
            return 1

        if args.context_check:
            print('PASS: Administrator database context valid')
            print('Database:', database)
            return 0

        databases = [database]

    if not databases:
        print('No SQLite databases found.')
        return 2

    failed = 0

    for database in databases:
        if not check_database(database):
            failed += 1

    print()
    print('Databases checked:', len(databases))
    print('Failed checks:', failed)

    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
