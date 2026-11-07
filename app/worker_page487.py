"""Release 487: sandboxed GET-only primary-page renderer for a secondary user.

The parent selects user identity through a verified server session. This
short-lived child revalidates the worker identity BEFORE importing app.db,
copies the private SQLite database into a disposable snapshot, and executes
real primary feature routers in an in-process ASGI harness. No HTTP listener,
user provisioning, live DB mutation, file download or browser write occurs.
Only bounded, inert plain text is returned to the parent gateway.
"""

import json
import os
import sqlite3
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote

MAX_REQUEST487 = 2048
MAX_TEXT487 = 18000

FEATURES487 = {
    "/": "dashboard",
    "/compounds": "compounds",
    "/vials": "vials",
    "/labs": "labs",
    "/protocols": "protocols",
    "/doses": "doses",
    "/vitals": "vitals",
    "/food": "food",
}


def parse_request487(raw):
    """Parse a strictly allowlisted request, never caller-selected identity."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_REQUEST487:
        raise ValueError("Invalid private route request length")

    def unique(pairs):
        values = {}
        for key, value in pairs:
            if key in values:
                raise ValueError("Duplicate request field")
            values[key] = value
        return values

    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except (UnicodeError, ValueError) as error:
        raise ValueError("Invalid private route JSON") from error

    if type(data) is not dict or set(data) != {"route", "query"}:
        raise ValueError("Unexpected private route fields")

    route, query = data["route"], data["query"]
    if type(route) is not str or route not in FEATURES487:
        raise ValueError("Private route not allowed")
    if type(query) is not dict or any(
        type(k) is not str or type(v) is not str
        for k, v in query.items()
    ):
        raise ValueError("Invalid route query")

    allowed = (
        {"day"} if route == "/food"
        else {"q"} if route == "/compounds"
        else set()
    )
    if not set(query) <= allowed or any(len(v) > 96 for v in query.values()):
        raise ValueError("Unexpected route parameters")

    if "day" in query:
        from datetime import date
        if date.fromisoformat(query["day"]).isoformat() != query["day"]:
            raise ValueError("Invalid journal date")

    return route, query


class _InertText487(HTMLParser):
    """Strip executable HTML, links, forms and attributes completely."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []
        self.size = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "template", "svg"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "template", "svg"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if self.hidden or self.size >= MAX_TEXT487:
            return
        text = " ".join(data.split())
        if text:
            text = text[: MAX_TEXT487 - self.size]
            self.parts.append(text)
            self.size += len(text)

    def text(self):
        return "\n".join(self.parts)


def _snapshot_private487(uid, private, target):
    source = private / "tracker.db"
    uri = "file:" + quote(str(source), safe="/") + "?mode=ro"

    with sqlite3.connect(uri, uri=True, timeout=15) as src:
        if src.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise RuntimeError("Private workspace integrity check failed")
        marker = src.execute("""
            SELECT user_id,status,schema_version
            FROM tracker_staged_workspace426
        """).fetchall()
        if marker != [(uid, "inactive", 426)]:
            raise RuntimeError("Private workspace identity mismatch")

        with sqlite3.connect(str(target), timeout=15) as dst:
            src.backup(dst, pages=256, sleep=0.05)

    target.chmod(0o600)


def render_page487(uid, private, route, query):
    with tempfile.TemporaryDirectory(prefix="tracker-private-487-") as directory:
        root = Path(directory)
        _snapshot_private487(uid, private, root / "tracker.db")

        # Must happen before app.db, app.config or app.main is imported.
        os.environ["TRACKER_DATA_DIR"] = str(root)
        os.environ["TRACKER_BACKUP_DIR"] = str(root / "backups")

        from . import config, session_auth385
        from .db import engine, SessionLocal
        from .routers import (
            dashboard, compounds, vials, labs, protocols, doses, vitals,
            food, food_quick375,
        )
        from .main import lifespan
        from .security import require_auth
        from fastapi import Depends, FastAPI
        from fastapi.routing import APIRoute
        from fastapi.testclient import TestClient

        if (
            session_auth385.enabled()
            or config.DATA_DIR != root
            or config.DB_PATH != root / "tracker.db"
            or Path(engine.url.database or "").absolute()
                != root / "tracker.db"
            or engine.url.get_backend_name() != "sqlite"
            or SessionLocal.kw.get("bind") is not engine
            or food.engine is not engine
            or food_quick375.engine is not engine
        ):
            raise RuntimeError("Private snapshot engine isolation failure")

        modules = {
            "/": dashboard, "/compounds": compounds,
            "/vials": vials, "/labs": labs,
            "/protocols": protocols, "/doses": doses,
            "/vitals": vitals, "/food": food,
        }
        module = modules[route]

        if not any(
            isinstance(item, APIRoute)
            and item.path == route and "GET" in item.methods
            for item in module.router.routes
        ):
            raise RuntimeError("Primary feature router unavailable")

        harness = FastAPI(
            dependencies=[Depends(require_auth)],
            lifespan=lifespan,
            docs_url=None, redoc_url=None, openapi_url=None,
        )
        harness.include_router(module.router)

        with TestClient(
            harness, base_url="https://private-worker.invalid"
        ) as client:
            response = client.get(
                route,
                params=query,
                auth=(os.environ["TRACKER_USER"], os.environ["TRACKER_PASS"]),
                follow_redirects=False,
            )

        if (
            response.status_code != 200
            or not response.headers.get("content-type", "").startswith("text/html")
        ):
            raise RuntimeError("Private page did not return authenticated HTML")

        parser = _InertText487()
        parser.feed(response.text)
        result = parser.text()
        if not result:
            raise RuntimeError("Private page empty after sanitization")

        return {
            "mode": "private-page-snapshot487",
            "user_id": uid,
            "route": route,
            "page_status": 200,
            "inert_text": result,
            "snapshot_only": True,
            "network_listener": False,
        }


def main():
    # This import is safe before configured database/app imports.
    from .worker_probe428 import validate_environment
    uid, private = validate_environment()
    route, query = parse_request487(
        sys.stdin.buffer.read(MAX_REQUEST487 + 1)
    )
    data = render_page487(uid, private, route, query)
    sys.stdout.write(json.dumps(data, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
