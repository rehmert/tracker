"""Release 465: read-only staged-account readiness.

Never activates accounts, modifies permissions, retrieves
password hashes, chooses an arbitrary browser-supplied user,
or permits cross-user database access.
"""
import json
from .instance_parity523 import interactive_parity523
from html import escape

REQUIRED_ACCOUNT_FIELDS = frozenset({
    "user_id", "username", "credential_status",
    "workspace_status", "login_enabled",
    "live_data_access_enabled",
})


def normalize_account465(record):
    if type(record) is not dict:
        raise ValueError("Invalid account record")
    if set(record) != REQUIRED_ACCOUNT_FIELDS:
        raise ValueError("Invalid account fields")

    uid = record["user_id"]
    username = record["username"]
    credentials = record["credential_status"]
    workspace = record["workspace_status"]

    if (
        type(uid) is not int or uid <= 1
        or type(username) is not str
        or not 2 <= len(username) <= 80
        or credentials != "disabled"
        or workspace != "inactive"
        or record["login_enabled"] is not False
        or record["live_data_access_enabled"] is not False
    ):
        raise ValueError("Account is not safely staged")

    return {
        "user_id": uid,
        "username": username,
        "credential_status": "disabled",
        "workspace_status": "inactive",
        "normal_login_enabled": False,
        "live_data_access_enabled": False,
        "pilot_login_only": True,
    }


def render_account465(record):
    account = normalize_account465(record)

    username = escape(account["username"], quote=True)
    uid = account["user_id"]

    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport"
content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>My Account · Tracker</title>
<style>
*{{box-sizing:border-box}}
body{{font:16px/1.5 system-ui,sans-serif;
margin:0;background:#f3f6fa;color:#182333}}
main{{max-width:680px;margin:auto;padding:16px}}
section{{padding:16px;background:white;border:1px
solid #cdd7e2;border-radius:12px;margin:14px 0}}
dt{{font-weight:700;margin-top:12px}}
dd{{margin:2px 0 10px;color:#415366}}
nav{{display:flex;flex-wrap:wrap;gap:10px}}
nav a{{display:inline-flex;min-height:44px;
align-items:center;padding:10px;
background:#e3eef8;border-radius:8px;color:#164f85}}
.note{{color:#415366}}
</style></head><body><main>
<nav>
<a href="/secondary/overview">Workspace</a>
<a href="/secondary/readiness">Feature Readiness</a>
<a href="/secondary/security">Session Security</a>
</nav>
<h1>My Account</h1>
<section>
<dl>
<dt>Username</dt><dd>{username}</dd>
<dt>Account Number</dt><dd>{uid}</dd>
<dt>Workspace</dt><dd>Private, staged and inactive</dd>
<dt>Normal Tracker Login</dt><dd>Disabled</dd>
<dt>Private Workspace Login</dt><dd>Available</dd>
<dt>Private Workspace</dt><dd>Available through unified login</dd>
</dl>
</section>
<section>
<h2>Account Security</h2>
<p class="note">Your pilot session is separate from
normal Tracker administrator authentication.</p>
<p>Use Session Security to change your password,
review active sessions or sign out other devices.</p>
<p>Activation into normal multi-user login is
not available in this pilot.</p>
</section>
</main></body></html>'''


def audit_accounts465(accounts):
    if type(accounts) is not list:
        raise ValueError("Invalid account inventory")

    result = []
    seen_ids = set()
    seen_names = set()

    for item in accounts:
        normalized = normalize_account465(item)
        uid = normalized["user_id"]
        name = normalized["username"].casefold()

        if uid in seen_ids or name in seen_names:
            raise ValueError("Duplicate account identity")

        seen_ids.add(uid)
        seen_names.add(name)
        result.append(normalized)

    return {
        "mode": "read-only-secondary-audit465",
        "staged_account_count": len(result),
        "all_accounts_inactive": True,
        "normal_multi_user_login_enabled": False,
        "accounts": result,
    }


def main():
    import os
    from . import config
    from .user_accounts427 import list_staged_accounts427

    if not interactive_parity523():
        raise PermissionError("Private workspace access disabled")

    if os.getenv("TRACKER_SECONDARY_LOCKDOWN440") == "1":
        raise PermissionError("Secondary preview locked down")

    accounts = list_staged_accounts427()
    print(json.dumps(
        audit_accounts465(accounts),
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
