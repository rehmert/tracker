"""Release 466: DEV-only multi-user cutover assessment.

No activation, session creation, account mutation, database
migration or cross-user data access is permitted.
"""
import json
import sys
from html import escape

from .instance_parity523 import interactive_parity523
from . import config, session_auth385 as auth
from .secondary_account_readiness465 import (
    normalize_account465,
)
from .user_accounts427 import (
    list_staged_accounts427,
    staging_environment,
)
from .user_storage388 import (
    planned_storage,
    live_storage_for,
)

BLOCKERS466 = (
    "Normal application login accepts only administrator sessions",
    "Global application database and ORM engine are administrator-scoped",
    "Secondary workspaces are marked inactive",
    "Production-ready per-user request routing is not implemented",
)

CHECKS466 = (
    "dev_environment",
    "administrator_session_mode",
    "staged_credentials_locked",
    "private_storage_separated",
    "normal_secondary_access_denied",
)


def validate_report466(report):
    if (
        type(report) is not dict
        or set(report) != {
            "mode", "checks", "staged_account_count",
            "staged_user_ids", "cutover_blockers",
            "normal_login_ready", "production_ready",
        }
        or report["mode"] != "offline-cutover-rehearsal466"
        or type(report["checks"]) is not dict
        or set(report["checks"]) != set(CHECKS466)
        or any(
            type(value) is not bool or not value
            for value in report["checks"].values()
        )
        or type(report["staged_account_count"]) is not int
        or report["staged_account_count"] < 0
        or type(report["staged_user_ids"]) is not list
        or len(report["staged_user_ids"]) !=
        report["staged_account_count"]
        or any(
            type(uid) is not int or uid <= 1
            for uid in report["staged_user_ids"]
        )
        or len(set(report["staged_user_ids"])) !=
        len(report["staged_user_ids"])
        or report["cutover_blockers"] != list(BLOCKERS466)
        or report["normal_login_ready"] is not False
        or report["production_ready"] is not False
    ):
        raise ValueError("Invalid cutover readiness report")

    return report


def assess_cutover466():
    """Offline administrator audit; no user-selected arguments."""
    if not interactive_parity523() or not auth.enabled():
        raise PermissionError("DEV session mode required")

    root = staging_environment()
    accounts = list_staged_accounts427()

    admin_paths = planned_storage(1, root)
    user_ids = []
    private_paths = set()

    for record in accounts:
        checked = normalize_account465(record)
        uid = checked["user_id"]
        paths = planned_storage(uid, root)

        if (
            uid in user_ids
            or paths.database == admin_paths.database
            or paths.database in private_paths
            or not paths.database.is_file()
            or paths.root != root / "users" / str(uid)
        ):
            raise RuntimeError(
                "Private database separation check failed"
            )

        private_paths.add(paths.database)
        user_ids.append(uid)

    # This must continue denying ordinary application
    # database access to secondary users.
    try:
        live_storage_for(2)
    except PermissionError:
        pass
    else:
        raise RuntimeError(
            "Normal secondary data access unexpectedly enabled"
        )

    report = {
        "mode": "offline-cutover-rehearsal466",
        "checks": {
            "dev_environment": True,
            "administrator_session_mode": True,
            "staged_credentials_locked": True,
            "private_storage_separated": True,
            "normal_secondary_access_denied": True,
        },
        "staged_account_count": len(user_ids),
        "staged_user_ids": user_ids,
        "cutover_blockers": list(BLOCKERS466),
        "normal_login_ready": False,
        "production_ready": False,
    }

    return validate_report466(report)


def render_cutover466(account):
    """Current user's stage only; no other account data."""
    account = normalize_account465(account)

    username = escape(account["username"], quote=True)
    uid = account["user_id"]

    blockers = "".join(
        "<li>" + escape(item) + "</li>"
        for item in BLOCKERS466
    )

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport"
content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Cutover Readiness · Tracker</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#f3f6fa;color:#182333;
font:16px/1.5 system-ui,sans-serif}}
main{{max-width:760px;margin:auto;padding:16px}}
section{{background:white;padding:16px;
border:1px solid #ccd7e2;border-radius:12px;
margin:14px 0}}
nav{{display:flex;flex-wrap:wrap;gap:8px}}
nav a{{min-height:44px;display:inline-flex;
align-items:center;padding:10px;border-radius:8px;
background:#e4eef8;color:#154e80}}
li{{margin:8px 0}}
.status{{font-weight:700}}
.note{{color:#405166}}
</style>
</head>
<body><main>
<nav>
<a href="/secondary/overview">Workspace</a>
<a href="/secondary/account">My Account</a>
<a href="/secondary/readiness">Feature Readiness</a>
<a href="/secondary/security">Session Security</a>
<a href="/secondary/data-context">Data Context</a>
</nav>
<h1>Multi-User Cutover Readiness</h1>
<section>
<h2>Current Account</h2>
<p>Signed in as <strong>{username}</strong>
(account {uid}).</p>
<p class="status">Private workspace active;
normal application login not enabled.</p>
<p>Private staged workspace: inactive.</p>
<p class="note">The account remains isolated from
the administrator's main application database.</p>
</section>
<section>
<h2>Remaining Architectural Work</h2>
<ol>{blockers}</ol>
<p>No account activation or database migration
can be initiated from this page.</p>
</section>
</main></body></html>'''


def main():
    # No user-supplied ID, path, URL or feature switch.
    if len(sys.argv) != 1:
        raise ValueError(
            "This audit does not accept arguments"
        )

    report = assess_cutover466()
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
