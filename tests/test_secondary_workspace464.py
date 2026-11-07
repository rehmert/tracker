"""Release 464 workspace integration and isolation tests."""
import re

from app.secondary_hub464 import (
    SECTIONS,
    render_workspace_hub464,
    render_workspace_nav464,
)


def test_hub464_allowlisted_routes_and_flags():
    capabilities = {
        section[3]: False for section in SECTIONS
    }
    html = render_workspace_hub464(capabilities)

    assert "My Workspace" in html
    assert "Food &amp; Water" in html
    assert "Write action disabled" in html
    assert 'href="/secondary/food"' in html
    assert 'href="/secondary/food/new"' not in html
    assert re.search(
        r'data-workspace-feature="food"', html
    )

    capabilities["food"] = True
    capabilities["vitals"] = True
    enabled = render_workspace_hub464(capabilities)

    assert 'href="/secondary/food/new"' in enabled
    assert 'href="/secondary/vitals/new"' in enabled
    assert 'href="/secondary/doses/new"' not in enabled
    assert "Logging enabled in DEV" in enabled

    navigation = render_workspace_nav464()
    assert 'href="/secondary/security"' in navigation
    assert 'href="/secondary/readiness"' in navigation


def test_hub464_rejects_untrusted_capabilities():
    import pytest

    original = {item[3]: False for item in SECTIONS}

    for invalid in (
        {"user_id": 3, **original},
        dict(original, food="true"),
        {"food": True},
    ):
        with pytest.raises(ValueError):
            render_workspace_hub464(invalid)
