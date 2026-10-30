#!/usr/bin/env python3
"""Tracker SQLite maintenance and diagnostics."""

import argparse
import json
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path


def connect_readonly(path):
    path = Path(path).resolve()

    if not path.is_file():
        raise FileNotFoundError(path)

    connection = sqlite3.connect(
        path.as_uri() + "?mode=ro",
        uri=True,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")

    return connection


def integrity(path):
    with connect_readonly(path) as db:
        structural = [
            row[0]
            for row in db.execute(
                "PRAGMA integrity_check"
            )
        ]

        foreign_keys = [
            list(row)
            for row in db.execute(
                "PRAGMA foreign_key_check"
            )
        ]

    return {
        "structural_integrity": (
            structural == ["ok"]
        ),
        "structural_details": structural,
        "foreign_key_integrity": (
            len(foreign_keys) == 0
        ),
        "foreign_key_violations": foreign_keys,
    }


def inventory(path):
    with connect_readonly(path) as db:
        tables = [
            row["name"]
            for row in db.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            )
        ]

        results = []

        for table in tables:
            quoted = (
                '"' + table.replace('"', '""') + '"'
            )

            count = db.execute(
                f"SELECT COUNT(*) FROM {quoted}"
            ).fetchone()[0]

            columns = [
                {
                    "name": row["name"],
                    "type": row["type"],
                    "primary_key": bool(row["pk"]),
                }
                for row in db.execute(
                    f"PRAGMA table_info({quoted})"
                )
            ]

            indexes = []

            for row in db.execute(
                f"PRAGMA index_list({quoted})"
            ):
                name = row["name"]

                index_quoted = (
                    '"' + name.replace('"', '""') + '"'
                )

                index_columns = [
                    item["name"]
                    for item in db.execute(
                        f"PRAGMA index_info({index_quoted})"
                    )
                ]

                indexes.append({
                    "name": name,
                    "unique": bool(row["unique"]),
                    "columns": index_columns,
                })

            results.append({
                "table": table,
                "rows": count,
                "columns": columns,
                "indexes": indexes,
            })

    return results


def snapshot(source, destination):
    source = Path(source).resolve()
    destination = Path(destination).resolve()

    if not source.is_file():
        raise FileNotFoundError(source)

    if destination.exists():
        raise FileExistsError(destination)

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # SQLite backup API creates a transactionally
    # consistent snapshot of an active database.
    try:
        with connect_readonly(source) as src:
            with sqlite3.connect(destination) as dst:
                src.backup(
                    dst,
                    pages=256,
                    sleep=0.1,
                )

        result = integrity(destination)

        if not (
            result["structural_integrity"]
            and result["foreign_key_integrity"]
        ):
            raise RuntimeError(
                "Snapshot verification failed: "
                + json.dumps(result)
            )

        return result

    except Exception:
        destination.unlink(missing_ok=True)
        raise


def database_metadata(path):
    path = Path(path).resolve()

    with connect_readonly(path) as db:
        page_count = db.execute(
            "PRAGMA page_count"
        ).fetchone()[0]

        page_size = db.execute(
            "PRAGMA page_size"
        ).fetchone()[0]

        journal_mode = db.execute(
            "PRAGMA journal_mode"
        ).fetchone()[0]

        user_version = db.execute(
            "PRAGMA user_version"
        ).fetchone()[0]

    return {
        "database": str(path),
        "file_bytes": path.stat().st_size,
        "logical_bytes": page_count * page_size,
        "journal_mode": journal_mode,
        "user_version": user_version,
    }


def report(path):
    return {
        "generated_at": datetime.now().isoformat(),
        "metadata": database_metadata(path),
        "integrity": integrity(path),
        "tables": inventory(path),
    }


def selftest():
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)

        source = directory / "test.sqlite3"
        backup = directory / "backup.sqlite3"

        with sqlite3.connect(source) as db:
            db.execute(
                "PRAGMA foreign_keys=ON"
            )

            db.execute(
                """
                CREATE TABLE parent (
                    id INTEGER PRIMARY KEY,
                    name TEXT
                )
                """
            )

            db.execute(
                """
                CREATE TABLE child (
                    id INTEGER PRIMARY KEY,
                    parent_id INTEGER REFERENCES parent(id)
                )
                """
            )

            db.execute(
                "INSERT INTO parent VALUES (1, 'test')"
            )

            db.execute(
                "INSERT INTO child VALUES (1, 1)"
            )

            db.execute(
                "CREATE INDEX child_parent_idx "
                "ON child(parent_id)"
            )

            db.commit()

        before = report(source)

        assert before["integrity"][
            "structural_integrity"
        ]

        assert before["integrity"][
            "foreign_key_integrity"
        ]

        snapshot(source, backup)

        after = report(backup)

        assert after["integrity"][
            "structural_integrity"
        ]

        assert after["integrity"][
            "foreign_key_integrity"
        ]

        assert len(after["tables"]) == 2

        assert sum(
            table["rows"]
            for table in after["tables"]
        ) == 2

        print("Maintenance self-test: PASS")


def main():
    parser = argparse.ArgumentParser(
        description="Tracker SQLite maintenance"
    )

    parser.add_argument(
        "command",
        choices=(
            "check",
            "report",
            "snapshot",
            "selftest",
        ),
    )

    parser.add_argument(
        "--database",
        help="Path to SQLite database",
    )

    parser.add_argument(
        "--output",
        help="Output JSON or snapshot filename",
    )

    args = parser.parse_args()

    if args.command == "selftest":
        selftest()
        return 0

    if not args.database:
        parser.error(
            "--database is required"
        )

    if args.command == "check":
        result = integrity(args.database)

    elif args.command == "report":
        result = report(args.database)

    else:
        if not args.output:
            parser.error(
                "--output is required for snapshot"
            )

        result = snapshot(
            args.database,
            args.output,
        )

    output = json.dumps(
        result,
        indent=2,
        default=str,
    )

    if args.command == "report" and args.output:
        destination = Path(args.output)
        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        destination.write_text(output + "\n")
        print(f"Report written to {destination}")
    else:
        print(output)

    if args.command == "check":
        if not (
            result["structural_integrity"]
            and result["foreign_key_integrity"]
        ):
            return 1

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(
            f"Maintenance error: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
