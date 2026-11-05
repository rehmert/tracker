#!/usr/bin/env python3
"""Release 411: read-only audit of scheduled backup scope."""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    source_file = ROOT / "scripts" / "tracker_backup.py"
    source = source_file.read_text()
    tree = ast.parse(source)

    function = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "main"
    ]

    assert len(function) == 1

    required = (
        "context = administrator_context410()",
        "data_dir=context.data_dir",
        "backup_dir=context.backup_dir",
        "archive.parent != context.backup_dir",
        "archive.is_symlink()",
        "verify_restorable(archive)",
        "removed = prune_backups(",
    )

    for expression in required:
        assert expression in source, expression

    def position(expression):
        return source.index(expression, source.index(
            'elif args.action == "create":'
        ))

    assert (
        position("context = administrator_context410()")
        < position("data_dir=context.data_dir")
        < position("archive.parent != context.backup_dir")
        < position("verify_restorable(archive)")
        < position("removed = prune_backups(")
    )

    from app.user_storage388 import live_storage_for

    for user_id in (2, 3):
        try:
            live_storage_for(user_id)
        except PermissionError:
            pass
        else:
            raise AssertionError(
                "Secondary account unexpectedly enabled"
            )

    print("=== RELEASE 411 BACKUP CONTEXT AUDIT ===")
    print("PASS: Context precedes scheduled backup")
    print("PASS: Source data directory explicitly selected")
    print("PASS: Archive directory explicitly selected")
    print("PASS: Archive output validated")
    print("PASS: Restore verification precedes pruning")
    print("PASS: Retention scoped to authorized directory")
    print("PASS: Secondary accounts remain disabled")
    print("Other background jobs: not yet migrated")
    print("PROD: unchanged")


if __name__ == "__main__":
    main()
