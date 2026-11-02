"""Read-only FastAPI smoke checks for every link in Tracker's actual sidebar.

tests/conftest.py configures a disposable SQLite database before app import.
No production database, service or browser is accessed.
"""
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from app.main import app


class SidebarLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_sidebar = False
        self.paths = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "nav" and attrs.get("id") == "app-sidebar":
            self.in_sidebar = True
        if self.in_sidebar and tag == "a":
            href = attrs.get("href", "")
            if href.startswith("/") and not href.startswith("//"):
                self.paths.append(href.split("?", 1)[0])

    def handle_endtag(self, tag):
        if tag == "nav" and self.in_sidebar:
            self.in_sidebar = False


@pytest.fixture(scope="module")
def client():
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def sidebar_routes(client):
    response = client.get("/")
    assert response.status_code == 200, f"Dashboard HTTP {response.status_code}"
    parser = SidebarLinks()
    parser.feed(response.text)
    paths = list(dict.fromkeys(parser.paths))
    assert len(paths) >= 35, (
        f"Expected substantial sidebar coverage; found {len(paths)}"
    )
    for required in (
        "/", "/record-explorer/vials", "/record-explorer/notes",
        "/record-explorer/database", "/record-explorer/health",
        "/maintenance-review", "/audit-history", "/backups",
        "/vials", "/doses", "/protocols", "/labs",
    ):
        assert required in paths, f"Missing sidebar destination {required}"
    return paths


def test_sidebar_destinations_have_registered_get_handlers(sidebar_routes):
    routes = [
        route for route in app.routes
        if "GET" in (getattr(route, "methods", None) or ())
    ]
    missing = [
        path for path in sidebar_routes
        if not any(route.path == path for route in routes)
    ]
    assert not missing, f"Sidebar destinations without GET handlers: {missing}"


def test_every_sidebar_page_renders_without_server_error(client, sidebar_routes):
    failures = []
    for path in sidebar_routes:
        try:
            response = client.get(path, follow_redirects=False)
            status = response.status_code
            content_type = response.headers.get("content-type", "")
            if status != 200 or "text/html" not in content_type:
                failures.append(
                    f"{path}: HTTP {status}, type {content_type[:45]}"
                )
            elif "<title>" not in response.text:
                failures.append(f"{path}: missing page title")
        except Exception as exc:
            failures.append(
                f"{path}: {type(exc).__name__}: {str(exc)[:120]}"
            )

    assert not failures, (
        f"{len(failures)} of {len(sidebar_routes)} sidebar pages failed:\n"
        + "\n".join(failures)
    )


def test_health_endpoints_remain_available(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert client.get("/ping").status_code == 200
