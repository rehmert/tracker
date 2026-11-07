"""Single-administrator security settings; DEV only."""

from datetime import datetime, timezone
from html import escape

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import session_auth385 as auth
from ..csrf_runtime import load_key
from ..csrf_tokens import issue_token, verify_pair

router = APIRouter()
CSRF_COOKIE = "tracker_account_csrf386"


def require_session(request):
    if not auth.enabled():
        raise HTTPException(404, "Unavailable")

    token = request.cookies.get(auth.COOKIE)
    username = auth.current_admin(token)
    if username is None:
        raise HTTPException(401, "Session required")

    return token, username


def reject_foreign(request):
    if request.headers.get(
        "sec-fetch-site", ""
    ).strip().lower() == "cross-site":
        raise HTTPException(403, "Cross-site request denied")


def check_csrf(request, form):
    if not verify_pair(
        request.cookies.get(CSRF_COOKIE),
        str(form.get("csrf_token", "")),
        load_key(),
    ):
        raise HTTPException(403, "Invalid account security token")


def page_html(username, sessions, csrf):
    username = escape(username)
    csrf = escape(csrf, quote=True)

    active = len(sessions)
    records = []

    for item in sessions:
        stamp = datetime.fromtimestamp(
            item["expires_at"], timezone.utc
        ).strftime("%Y-%m-%d %H:%M UTC")
        label = "This device" if item["current"] else "Other session"
        records.append(
            f"<li>{escape(label)} — expires {escape(stamp)}</li>"
        )

    session_list = "".join(records)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Account Security · Tracker DEV</title>
<style>
:root {{color-scheme:light dark}}
* {{box-sizing:border-box}}
body {{font:16px system-ui,sans-serif;max-width:640px;
margin:auto;padding:18px;background:Canvas;color:CanvasText}}
h1 {{font-size:1.6rem}}
section {{border:1px solid #8885;border-radius:12px;
padding:18px;margin:18px 0}}
label {{display:block;margin:14px 0}}
input {{font:inherit;width:100%;padding:12px;
min-height:46px;border:1px solid #888;border-radius:8px}}
button {{min-height:46px;padding:10px 18px;font:inherit;
border-radius:8px;cursor:pointer}}
.primary {{background:#1265ad;color:white;border:0}}
.note {{font-size:.88rem;opacity:.85;line-height:1.5}}
li {{margin:8px 0}}
</style>
</head>
<body>
<p><a href="/">← Back to Tracker</a></p>
<h1>Account Security</h1>
<p><a href="/account/users">Manage Secondary Users</a></p>
<p>Signed in as <strong>{username}</strong>.</p>
<section>
<h2>Active Sessions</h2>
<p>{active} active session(s)</p>
<ul>{session_list}</ul>
<form method="post" action="/account/sessions/revoke-others">
<input type="hidden" name="csrf_token" value="{csrf}">
<button class="primary" type="submit">Sign Out Other Devices</button>
</form>
</section>
<section>
<h2>Change Password</h2>
<p class="note">Changing your password signs out every device,
including this one. Sign in again with your new password.</p>
<form method="post" action="/account/password">
<input type="hidden" name="csrf_token" value="{csrf}">
<label>Current Password
<input type="password" name="current_password"
autocomplete="current-password" required></label>
<label>New Password (12 characters minimum)
<input type="password" name="new_password"
autocomplete="new-password" minlength="12" required></label>
<label>Confirm New Password
<input type="password" name="confirm_password"
autocomplete="new-password" minlength="12" required></label>
<button class="primary" type="submit">Change Password</button>
</form>
</section>
<p class="note">This release supports one administrator only.
Other user accounts remain disabled until data isolation is implemented.</p>
</body>
</html>"""


@router.get("/account/security")
def account_page(request: Request):
    token, username = require_session(request)
    csrf = issue_token(load_key())
    sessions = auth.session_overview(token)

    response = HTMLResponse(
        page_html(username, sessions, csrf),
        headers={"Cache-Control": "no-store"},
    )
    response.set_cookie(
        CSRF_COOKIE, csrf, secure=True, httponly=True,
        samesite="strict", max_age=900, path="/account",
    )
    return response


@router.post("/account/sessions/revoke-others")
async def revoke_others(request: Request):
    token, _ = require_session(request)
    reject_foreign(request)
    form = await request.form()
    check_csrf(request, form)
    auth.revoke_other_sessions(token)

    return RedirectResponse(
        "/account/security",
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )


@router.post("/account/password")
async def password_change(request: Request):
    token, _ = require_session(request)
    reject_foreign(request)
    form = await request.form()
    check_csrf(request, form)

    current = str(form.get("current_password", ""))
    new = str(form.get("new_password", ""))
    confirm = str(form.get("confirm_password", ""))

    if new != confirm or not auth.change_password(
        token, current, new
    ):
        return HTMLResponse(
            '<h1>Password Not Changed</h1>'
            '<p>Check the current password, new password '
            'and confirmation. The new password must '
            'contain at least 12 characters.</p>'
            '<p><a href="/account/security">Try Again</a></p>',
            status_code=400,
            headers={"Cache-Control": "no-store"},
        )

    response = RedirectResponse(
        "/login", status_code=303,
        headers={"Cache-Control": "no-store"},
    )
    response.delete_cookie(
        auth.COOKIE, secure=True, httponly=True,
        samesite="lax", path="/",
    )
    return response
