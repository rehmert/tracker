"""Release 467 private request context security contracts."""

from pathlib import Path


def test_private_request_db467_is_fail_closed():
    source = Path(
        "app/secondary_request_db467.py"
    ).read_text()

    for marker in (
        "worker_plan428(uid)",
        "mode=ro",
        "PRAGMA query_only=ON",
        "tracker_staged_workspace426",
        "scope.user_id",
        "request.cookies.get(COOKIE)",
        "require_preview()",
    ):
        assert marker in source, marker

    assert "request.query_params" not in source
    assert "request.path_params" not in source
    assert "CREATE TABLE" not in source
    assert "INSERT INTO" not in source
    assert "UPDATE users" not in source


def test_private_request_db467_preserves_global_engine():
    from app import db, session_auth385
    from app.user_storage388 import live_storage_for

    assert db.SessionLocal is not None
    assert callable(session_auth385.verify_admin)

    try:
        live_storage_for(2)
    except PermissionError:
        pass
    else:
        raise AssertionError(
            "Normal secondary database access was enabled"
        )


def test_private_request_db467_router_is_get_only():
    from app.secondary_preview430 import preview_app

    methods = [
        (method, route.path)
        for route in preview_app.routes
        for method in getattr(route, "methods", set())
    ]

    assert methods.count(
        ("GET", "/data-context")
    ) == 1

    assert (
        "POST", "/data-context"
    ) not in methods
