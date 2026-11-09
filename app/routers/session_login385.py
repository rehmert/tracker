"""Browser login and logout for both environments."""

from html import escape

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import session_auth385 as auth
from ..unified_login473 import (
    enabled473,
    authenticate_secondary473,
)
from ..csrf_runtime import COOKIE_NAME, load_key
from ..csrf_tokens import issue_token, verify_pair

router = APIRouter()
LOGIN_CSRF = "tracker_login_csrf"


def build_login_html(destination, token, error=""):
    """Construct the login form with safely escaped attributes."""

    destination = escape(
        auth.safe_next(destination), quote=True
    )
    token = escape(token, quote=True)

    warning = (
        '<p role="alert">Sign-in unsuccessful. '
        'Check credentials or try again later.</p>'
        if error else ""
    )

    # All interpolations occur inside this complete f-string.
    # No nested or concatenated triple-quoted literals.
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Sign In · Tracker</title>
<style>
:root {{color-scheme:light dark}}
* {{box-sizing:border-box}}
body {{font:16px system-ui,sans-serif;margin:0;min-height:100vh;
display:grid;place-items:center;padding:18px;
background:Canvas;color:CanvasText}}
main {{width:min(100%,420px);padding:24px;
border:1px solid #8886;border-radius:14px}}
h1 {{font-size:1.5rem}}
label {{display:block;margin:16px 0}}
input[type=text],input[type=password] {{
width:100%;min-height:48px;padding:12px;
font:inherit;border:1px solid #888;border-radius:9px;
margin-top:6px}}
button {{width:100%;min-height:50px;font:inherit;
font-weight:700;border:0;border-radius:9px;
background:#1265ad;color:white}}
.remember {{display:flex;align-items:center;gap:10px}}
.remember input {{width:20px;height:20px}}
.note {{font-size:.85rem;opacity:.8}}
</style>
</head>
<body>
<main>
<h1>Tracker</h1>
<p>Sign in to your personal workspace.</p>
{warning}
<form method="post" action="/login">
<input type="hidden" name="next" value="{destination}">
<input type="hidden" name="csrf_token" value="{token}">
<label>Username
<input type="text" name="username"
autocomplete="username" maxlength="80" required autofocus>
</label>
<label>Password
<input type="password" name="password"
autocomplete="current-password" required>
</label>
<label class="remember">
<input type="checkbox" name="remember" value="yes" checked>
Keep me signed in on this device
</label>
<button type="submit">Sign In</button>
</form>
<p class="note">Use HTTPS. Do not remember a shared device.</p>
</main>
</body>
</html>"""


@router.get("/login")
def login_page(request: Request):
    if not auth.enabled():
        raise HTTPException(404, "Login unavailable")

    token = issue_token(load_key())

    html = build_login_html(
        request.query_params.get("next"),
        token,
    )

    response = HTMLResponse(
        html, headers={"Cache-Control": "no-store"}
    )

    response.set_cookie(
        LOGIN_CSRF,
        token,
        secure=True,
        httponly=True,
        samesite="strict",
        max_age=900,
        path="/",
    )

    return response


@router.post("/login")
async def login_submit(request: Request):
    if not auth.enabled():
        raise HTTPException(404, "Login unavailable")

    # Explicitly reject cross-site browser submissions.
    # Public HTTPS Origin may differ from the reverse proxy's
    # internal Host and is not used as the authorization proof.
    if request.headers.get(
        "sec-fetch-site", ""
    ).strip().lower() == "cross-site":
        raise HTTPException(403, "Cross-site login denied")

    form = await request.form()

    if not verify_pair(
        request.cookies.get(LOGIN_CSRF),
        str(form.get("csrf_token", "")),
        load_key(),
    ):
        raise HTTPException(403, "Invalid login token")

    username = str(form.get("username", "")).strip()[:80]
    password = str(form.get("password", ""))

    if len(password) > 1024:
        raise HTTPException(422, "Invalid credentials")

    if not auth.verify_admin(username, password):
        secondary = authenticate_secondary473(
            username, password
        )

        if secondary is not None:
            from ..secondary_preview430 import (
                COOKIE as SECONDARY_COOKIE,
                LIFETIME as SECONDARY_LIFETIME,
                _revoke as revoke_secondary,
            )

            uid, secondary_token = secondary
            if type(uid) is not int or uid <= 1:
                raise HTTPException(
                    503, "Secondary identity mismatch"
                )

            previous_admin = request.cookies.get(
                auth.COOKIE
            )
            if previous_admin:
                auth.revoke(previous_admin)

            previous_secondary = request.cookies.get(
                SECONDARY_COOKIE
            )
            if previous_secondary:
                revoke_secondary(previous_secondary)

            response = RedirectResponse(
                "/secondary/overview",
                status_code=303,
                headers={"Cache-Control": "no-store"},
            )

            response.delete_cookie(
                auth.COOKIE,
                path="/",
                secure=True,
                httponly=True,
                samesite="lax",
            )

            # Unified login uses a root-path cookie so
            # subsequent /login requests can see and revoke
            # the previous secondary session.
            response.set_cookie(
                SECONDARY_COOKIE,
                secondary_token,
                secure=True,
                httponly=True,
                samesite="strict",
                path="/",
                max_age=SECONDARY_LIFETIME,
            )

            # Remove cookies issued by the original
            # /secondary/login implementation.
            response.delete_cookie(
                SECONDARY_COOKIE,
                path="/secondary",
                secure=True,
                httponly=True,
                samesite="strict",
            )

            response.delete_cookie(
                LOGIN_CSRF,
                path="/",
                secure=True,
                httponly=True,
                samesite="strict",
            )
            return response

        # A rejected credential must leave a usable login
        # form. Issue a fresh token paired with a fresh
        # secure cookie; never render an empty CSRF field.
        retry_token = issue_token(load_key())
        response = HTMLResponse(
            build_login_html(
                auth.safe_next(form.get("next")),
                retry_token,
                error="invalid",
            ),
            status_code=401,
            headers={"Cache-Control": "no-store"},
        )
        response.set_cookie(
            LOGIN_CSRF,
            retry_token,
            secure=True,
            httponly=True,
            samesite="strict",
            max_age=900,
            path="/",
        )
        return response

    token, lifetime = auth.create_session(
        form.get("remember") == "yes"
    )

    response = RedirectResponse(
        auth.safe_next(form.get("next")),
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )

    response.set_cookie(
        auth.COOKIE,
        token,
        secure=True,
        httponly=True,
        samesite="lax",
        max_age=lifetime,
        path="/",
    )

    # Switching back to administrator credentials
    # must revoke any previously active secondary session.
    if enabled473():
        from ..secondary_preview430 import (
            COOKIE as SECONDARY_COOKIE,
            _revoke as revoke_secondary,
        )

        previous_secondary = request.cookies.get(
            SECONDARY_COOKIE
        )

        if previous_secondary:
            revoke_secondary(previous_secondary)

        response.delete_cookie(
            SECONDARY_COOKIE,
            path="/",
            secure=True,
            httponly=True,
            samesite="strict",
        )
        response.delete_cookie(
            SECONDARY_COOKIE,
            path="/secondary",
            secure=True,
            httponly=True,
            samesite="strict",
        )

    response.delete_cookie(
        LOGIN_CSRF,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )

    return response


@router.post("/logout")
async def logout(request: Request):
    if not auth.enabled():
        raise HTTPException(404, "Logout unavailable")

    if request.headers.get(
        "sec-fetch-site", ""
    ).strip().lower() == "cross-site":
        raise HTTPException(403, "Cross-site logout denied")

    form = await request.form()

    if not verify_pair(
        request.cookies.get(COOKIE_NAME),
        str(form.get("csrf_token", "")),
        load_key(),
    ):
        raise HTTPException(403, "Invalid logout token")

    auth.revoke(request.cookies.get(auth.COOKIE))

    response = RedirectResponse(
        "/login",
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )

    response.delete_cookie(
        auth.COOKIE,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )

    return response
