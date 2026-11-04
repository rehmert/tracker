"""Regression for the Release 190-205 source-formatting failure."""
from pathlib import Path
import ast


def test_regression_is_not_quote_sensitive():
    path=Path('tests/test_pk_142_145.py')
    source=path.read_text()

    assert 'assert \'"bulk_create"\' in routes' not in source
    ast.parse(source)


def test_release_gate_uses_isolated_data_and_full_suite():
    path=Path('scripts/tracker-release.sh').read_text()

    assert 'TRACKER_DATA_DIR' in path
    assert 'pytest' in path
    assert 'tracker-restore-verify.py' in path
