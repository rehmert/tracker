"""Release 468: authenticated ORM isolation contract."""

from pathlib import Path

import pytest

from app.secondary_orm468 import (
    COUNTS468,
    render_summary468,
)


def sample468():
    return {
        "mode": "private-orm-summary468",
        "user_id": 2,
        "storage_mode": "secondary-read-only",
        "read_only": True,
        "normal_login_enabled": False,
        "counts": {
            key: 0 for key in COUNTS468
        },
        "recent": {
            "vitals": [],
            "doses": [],
            "food": [
                {
                    "day": "2026-11-07",
                    "name": "<script>bad</script>",
                    "servings": 1,
                },
            ],
        },
    }


def test_orm468_escapes_private_values():
    html = render_summary468(sample468())

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Private Data Summary" in html

    with pytest.raises(ValueError):
        render_summary468(
            dict(sample468(), read_only=False)
        )

    with pytest.raises(ValueError):
        render_summary468(
            dict(sample468(), user_id=1)
        )


def test_orm468_readonly_engine_contract():
    source = Path(
        "app/secondary_orm468.py"
    ).read_text()

    for required in (
        "verified_private_scope467(request)",
        "poolclass=NullPool",
        "mode=ro&uri=true",
        "PRAGMA query_only=ON",
        "tracker_staged_workspace426",
        "engine.dispose()",
        "LIMIT 5",
    ):
        assert required in source, required

    for forbidden in (
        "from .db import engine",
        "from .db import SessionLocal",
        "UPDATE users",
        "DELETE FROM users",
        "INSERT INTO users",
        "set_cookie(",
        "request.query_params",
        "request.path_params",
    ):
        assert forbidden not in source, forbidden


def test_orm468_routes_are_get_only():
    from app.secondary_preview430 import preview_app

    methods = [
        (method, route.path)
        for route in preview_app.routes
        for method in getattr(route, "methods", set())
    ]

    for route in (
        "/orm-summary",
        "/orm-summary.json",
    ):
        assert methods.count(("GET", route)) == 1
        assert ("POST", route) not in methods
