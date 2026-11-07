"""Administrator-only DEV secondary account creation."""
from html import escape

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import config, session_auth385 as auth
from ..csrf_runtime import load_key
from ..csrf_tokens import issue_token, verify_pair
from ..secondary_provision479 import create_secondary_user479
from ..user_accounts427 import list_staged_accounts427

router = APIRouter()
CSRF_COOKIE = "tracker_users_csrf479"


def _admin479(request):
    if config.instance_label() != "DEV" or not auth.enabled():
        raise HTTPException(404, "Unavailable")

    if auth.session_user(
        request.cookies.get(auth.COOKIE)
    ) != 1:
        raise HTTPException(403, "Administrator required")


def _accounts479():
    try:
        return list_staged_accounts427()
    except (RuntimeError, PermissionError, OSError, ValueError):
        raise HTTPException(
            503, "Account inventory unavailable"
        ) from None


def _html479(accounts, token, created=False):
    rows = "".join(
        "<tr><td>" + str(a["user_id"]) + "</td><td>"
        + escape(a["username"]) + "</td>"
        "<td>Private workspace</td></tr>"
        for a in accounts
    )

    if not rows:
        rows = (
            '<tr><td colspan="3">No secondary users</td></tr>'
        )

    notice = (
        '<p role="status">Account created successfully.</p>'
        if created else ""
    )

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>User Management · Tracker DEV</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#f3f6fa;color:#192638;
font:16px/1.5 system-ui,sans-serif}}
main{{max-width:800px;margin:auto;padding:16px}}
section{{background:white;border:1px solid #d0d8e2;
border-radius:12px;padding:18px;margin:18px 0}}
h1{{font-size:1.7rem}}
label{{display:block;font-weight:600;margin:14px 0}}
input{{display:block;width:100%;font:inherit;
min-height:48px;padding:10px;border:1px solid #8996a5;
border-radius:8px;margin-top:5px}}
button{{min-height:48px;padding:10px 18px;
font:inherit;background:#195d95;color:white;
border:0;border-radius:8px}}
table{{width:100%;border-collapse:collapse}}
th,td{{padding:10px;text-align:left;
border-bottom:1px solid #e2e8f0}}
.scroll{{overflow-x:auto}}
.note{{font-size:.9rem;color:#43556b}}
</style>
</head>
<body><main>
<p><a href="/account/security">Account Security</a>
 · <a href="/">Tracker Home</a></p>
<h1>User Management</h1>
<p>Administrator only · DEV secondary workspaces</p>
{notice}
<section>
<h2>Secondary Users ({len(accounts)})</h2>
<div class="scroll">
<table>
<thead><tr><th>ID</th><th>Username</th>
<th>Storage</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>
</section>
<section>
<h2>Create Secondary User</h2>
<form method="post" action="/account/users">
<input type="hidden" name="csrf_token"
value="{escape(token, quote=True)}">
<label>Username
<input type="text" name="username"
autocomplete="off" minlength="2" maxlength="80"
required></label>
<label>Password
<input type="password" name="password"
autocomplete="new-password" maxlength="1024"
required></label>
<label>Confirm Password
<input type="password" name="confirmation"
autocomplete="new-password" maxlength="1024"
required></label>
<button type="submit">Create User</button>
</form>
<p class="note">No password minimum length or complexity
requirements. Blank passwords are rejected.
Private storage is created with the Tracker service
account's ownership.</p>
</section>
</main></body></html>'''


@router.get("/account/users")
def users_page479(request: Request):
    _admin479(request)

    token = issue_token(load_key())
    response = HTMLResponse(
        _html479(
            _accounts479(),
            token,
            request.query_params.get("created") == "1",
        ),
        headers={"Cache-Control": "no-store"},
    )
    response.set_cookie(
        CSRF_COOKIE, token,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/account",
        max_age=900,
    )
    return response


@router.post("/account/users")
async def create_user479(request: Request):
    _admin479(request)

    if (
        request.headers.get(
            "sec-fetch-site", ""
        ).strip().lower() == "cross-site"
    ):
        raise HTTPException(
            403, "Cross-site request rejected"
        )

    if request.query_params:
        raise HTTPException(
            400, "Unexpected query parameters"
        )

    form = await request.form()
    expected = {
        "csrf_token", "username",
        "password", "confirmation",
    }

    if set(form) != expected or any(
        len(form.getlist(name)) != 1
        for name in expected
    ):
        raise HTTPException(
            422, "Invalid account form"
        )

    if not verify_pair(
        request.cookies.get(CSRF_COOKIE),
        form.get("csrf_token"),
        load_key(),
    ):
        raise HTTPException(403, "Invalid form token")

    try:
        create_secondary_user479(
            form.get("username"),
            form.get("password"),
            form.get("confirmation"),
        )
    except ValueError:
        raise HTTPException(
            422, "Invalid username or password"
        ) from None
    except FileExistsError:
        raise HTTPException(
            409, "Account already exists"
        ) from None
    except (
        RuntimeError, PermissionError, OSError
    ):
        raise HTTPException(
            503, "Account provisioning unavailable"
        ) from None

    return RedirectResponse(
        "/account/users?created=1",
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )
