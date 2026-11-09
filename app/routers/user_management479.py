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
    if config.instance_label() not in ("DEV", "PROD") or not auth.enabled():
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
        "<td>Private workspace</td>"
        '<td><a href="/account/users/'
        + str(a["user_id"])
        + '/edit">Edit</a></td></tr>'
        for a in accounts
    )

    if not rows:
        rows = (
            '<tr><td colspan="4">No secondary users</td></tr>'
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
<th>Storage</th><th>Actions</th></tr></thead>
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


# Release 480: secondary-user editing.
from ..user_accounts427 import inspect_staged_account427
from ..secondary_account_edit480 import edit_secondary_account480


def _edit_html480(account, token, updated=False):
    uid = account["user_id"]
    username = escape(account["username"], quote=True)
    csrf = escape(token, quote=True)

    notice = (
        '<p role="status">Changes saved. Existing sessions '
        'for this user have been signed out.</p>'
        if updated else ""
    )

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Edit User · Tracker DEV</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#f3f6fa;color:#192638;
font:16px/1.5 system-ui,sans-serif}}
main{{max-width:640px;margin:auto;padding:16px}}
section{{background:white;border:1px solid #d0d8e2;
border-radius:12px;padding:18px;margin:18px 0}}
label{{display:block;font-weight:600;margin:16px 0}}
input{{display:block;width:100%;font:inherit;
min-height:48px;padding:10px;border:1px solid #8996a5;
border-radius:8px;margin-top:5px}}
button{{min-height:48px;padding:10px 18px;
font:inherit;background:#195d95;color:white;
border:0;border-radius:8px;cursor:pointer}}
.note{{font-size:.9rem;color:#43556b}}
</style>
</head>
<body><main>
<p><a href="/account/users">Back to User Management</a></p>
<h1>Edit Secondary User</h1>
<p>Account ID: <strong>{uid}</strong></p>
{notice}
<section>
<form method="post" action="/account/users/edit">
<input type="hidden" name="csrf_token" value="{csrf}">
<input type="hidden" name="user_id" value="{uid}">
<label>Username
<input type="text" name="username" value="{username}"
autocomplete="off" minlength="2" maxlength="80"
required></label>
<h2>Password Reset</h2>
<p class="note">Leave both fields blank to keep the
existing password.</p>
<label>New Password
<input type="password" name="password"
autocomplete="new-password" maxlength="1024"></label>
<label>Confirm New Password
<input type="password" name="confirmation"
autocomplete="new-password" maxlength="1024"></label>
<p class="note">Saving changes signs out this user's
existing sessions. Their private data and workspace
remain unchanged.</p>
<button type="submit">Save Changes</button>
</form>
</section>
</main></body></html>'''


@router.get("/account/users/{user_id}/edit")
def edit_page480(request: Request, user_id: int):
    _admin479(request)

    if user_id <= 1:
        raise HTTPException(404, "Secondary user not found")

    try:
        account = inspect_staged_account427(user_id)
    except (
        ValueError, RuntimeError, PermissionError, OSError
    ):
        raise HTTPException(
            404, "Secondary user not found"
        ) from None

    token = issue_token(load_key())
    response = HTMLResponse(
        _edit_html480(
            account,
            token,
            request.query_params.get("updated") == "1",
        ),
        headers={"Cache-Control": "no-store"},
    )
    response.set_cookie(
        CSRF_COOKIE,
        token,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/account",
        max_age=900,
    )
    return response


@router.post("/account/users/edit")
async def save_edit480(request: Request):
    _admin479(request)

    if request.headers.get(
        "sec-fetch-site", ""
    ).strip().lower() == "cross-site":
        raise HTTPException(403, "Cross-site request rejected")

    if request.query_params:
        raise HTTPException(400, "Unexpected query parameters")

    form = await request.form()
    expected = {
        "csrf_token", "user_id", "username",
        "password", "confirmation",
    }

    if set(form) != expected or any(
        len(form.getlist(name)) != 1
        for name in expected
    ):
        raise HTTPException(422, "Invalid edit form")

    if not verify_pair(
        request.cookies.get(CSRF_COOKIE),
        form.get("csrf_token"),
        load_key(),
    ):
        raise HTTPException(403, "Invalid form token")

    try:
        raw_uid = form.get("user_id")

        if (
            not isinstance(raw_uid, str)
            or not raw_uid.isdecimal()
        ):
            raise ValueError("Invalid user ID")

        uid = int(raw_uid)

        if uid <= 1:
            raise ValueError("Cannot edit administrator")

        password = form.get("password")
        confirmation = form.get("confirmation")

        if (
            not isinstance(password, str)
            or not isinstance(confirmation, str)
            or password != confirmation
        ):
            raise ValueError("Password confirmation mismatch")

        replacement = password if password else None

        edit_secondary_account480(
            uid,
            form.get("username"),
            replacement,
        )

    except (ValueError, TypeError):
        raise HTTPException(422, "Invalid edit values") from None
    except FileExistsError:
        raise HTTPException(409, "Username already exists") from None
    except LookupError:
        raise HTTPException(404, "Secondary user not found") from None
    except (RuntimeError, PermissionError, OSError):
        raise HTTPException(
            503, "Account update unavailable"
        ) from None

    return RedirectResponse(
        f"/account/users/{uid}/edit?updated=1",
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )
