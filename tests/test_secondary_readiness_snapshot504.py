"""Release 504: guard the read-only readiness flag test speedup.

This test checks that only the repetitive flag-display GETs reuse one
previously validated snapshot. Real workers and all disabled POST security
checks must remain in the original integration test.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/test_secondary_integration440.py"


def test_504_readiness_snapshot_only_replaces_redundant_gets():
    source = SOURCE.read_text(encoding="utf-8")
    fn = next(
        node for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef)
        and node.name == "test_authenticated_readiness_matches_every_runtime_flag"
    )

    # The first /readiness GET has a REAL worker report captured for
    # inspection. An independent, real /overview request follows it.
    assert "report = actual_worker(uid)" in source
    assert 'page = client.get("/secondary/readiness")' in source
    assert 'client.get(\n        "/secondary/overview"' in source

    # Every toggle of the seven feature flags is still checked over HTTP.
    assert "for flag, name, route in FEATURES:" in source
    assert 'assert client.post(route, data={}).status_code == 404' in source
    assert 'final_page = client.get("/secondary/readiness")' in source

    # In the two snapshots used by the loop, only GET is called. No
    # disabled POST or final real worker check can execute under a stub.
    snapshot_contexts = [
        node for node in ast.walk(fn)
        if isinstance(node, ast.With)
        and any(
            isinstance(item.context_expr, ast.Call)
            and isinstance(item.context_expr.func, ast.Attribute)
            and item.context_expr.func.attr == "context"
            and isinstance(item.optional_vars, ast.Name)
            and item.optional_vars.id == "pinned_readonly"
            for item in node.items
        )
    ]
    assert len(snapshot_contexts) == 2
    for context in snapshot_contexts:
        calls = [
            node for statement in context.body for node in ast.walk(statement)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "client"
        ]
        assert len(calls) == 1
        assert calls[0].func.attr == "get"

    # Account identity remains fail-closed, and the snapshot cannot be
    # mutated between requests or shared with another workspace.
    assert 'if type(uid) is not int or uid != 2:' in source
    assert 'raise PermissionError("Unexpected workspace identity")' in source
    assert 'return deepcopy(private_report["result"])' in source
    assert 'with pytest.raises(PermissionError):' in source

    assert source.index(
        'final_page = client.get("/secondary/readiness")'
    ) > source.index(
        'assert client.post(route, data={}).status_code == 404'
    )
