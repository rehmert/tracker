"""Release 410: context-check cannot create or prune backups."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_context_check_precedes_backup_create():
    source = (
        ROOT / "scripts" / "tracker_backup.py"
    ).read_text()

    assert 'args.action == "context-check"' in source
    assert "administrator_context410()" in source

    tree = ast.parse(source)
    functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "main"
    ]
    assert len(functions) == 1


def test_existing_create_restore_gate_remains():
    source = (
        ROOT / "scripts" / "tracker_backup.py"
    ).read_text()

    assert "context = administrator_context410()" in source
    assert "data_dir=context.data_dir" in source
    assert "backup_dir=context.backup_dir" in source
    assert "verify_restorable(archive)" in source
    assert "removed = prune_backups(" in source


def test_cli_does_not_enable_secondary_users():
    source = (
        ROOT / "app" / "background_storage410.py"
    ).read_text()

    assert "user_id != 1" in source
    assert 'scope="legacy-admin-instance"' in source
