"""Release 486: DEV-only, read-only full-app route authorization PLAN.

This module is intentionally NOT registered on the running application.
It does not forward traffic, start worker processes, expose credentials,
or grant access to the administrator engine. The future private-process
gateway must call this verifier before choosing a user's worker.

Identity comes solely from an existing server-validated secondary session.
No HTTP-supplied user ID, private path, database name, or engine is trusted.
"""

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, Request

from . import config


# The initial read-only gateway is an explicit, fixed pilot route set.
# Do not silently expand it to file downloads or administrative routes.
READ_ONLY_PAGES486 = frozenset({
    "/", "/compounds", "/vials", "/labs",
    "/protocols", "/doses", "/vitals", "/food",
})
FORBIDDEN_QUERY_KEYS486 = frozenset({
    "user_id", "uid", "account_id", "tenant_id",
    "database", "db_path", "data_dir", "workspace_root",
})


@dataclass(frozen=True)
class VerifiedPrivateRoute486:
    user_id: int
    method: str
    route: str
    workspace_root: Path
    database: Path


def authorize_fullapp_route486(request: Request, relative_path: str):
    """Compute a server-owned private route plan, without invoking it.

    A future gateway must use this result to choose an isolated process;
    the HTTP request's query, path and headers never select a workspace.
    """
    from .secondary_preview430 import (
        COOKIE, _session_user, preview_enabled,
    )
    from .worker_scope428 import worker_plan428

    if (
        config.instance_label() != "DEV"
        or not preview_enabled()
        or os.getenv("TRACKER_FULLAPP_GATEWAY486", "0") != "1"
    ):
        raise HTTPException(404, "Private full-app gateway unavailable")

    if request.method != "GET":
        raise HTTPException(405, "Read-only gateway")

    if not isinstance(relative_path, str) or len(relative_path) > 96:
        raise HTTPException(400, "Invalid private route")

    # Exact path matching prevents escaping into administrator, user
    # management, backup, static-file or credential-management routes.
    selected = "/" + relative_path if relative_path else "/"

    if (
        selected not in READ_ONLY_PAGES486
        or not request.url.path.startswith("/secondary/full/")
        or b"%" in request.scope.get("raw_path", b"")
    ):
        raise HTTPException(404, "Private route not permitted")

    if any(
        key.casefold() in FORBIDDEN_QUERY_KEYS486
        for key in request.query_params.keys()
    ):
        raise HTTPException(400, "Client-supplied workspace selector")

    token = request.cookies.get(COOKIE)
    uid = _session_user(token)

    if type(uid) is not int or uid <= 1:
        raise HTTPException(401, "Secondary session required")

    try:
        storage = worker_plan428(uid)
    except (OSError, PermissionError, RuntimeError, ValueError, sqlite3.Error):
        raise HTTPException(
            503, "Verified private workspace unavailable"
        ) from None

    trusted_root = (Path(config.DATA_DIR) / "users" / str(uid)).absolute()

    if (
        storage.user_id != uid
        or storage.mode != "reserved-inactive"
        or storage.root != trusted_root
        or storage.database != trusted_root / "tracker.db"
        or storage.database.is_symlink()
        or not storage.database.is_file()
    ):
        raise HTTPException(
            503, "Verified private workspace mismatch"
        )

    return VerifiedPrivateRoute486(
        user_id=uid,
        method="GET",
        route=selected,
        workspace_root=trusted_root,
        database=storage.database,
    )
