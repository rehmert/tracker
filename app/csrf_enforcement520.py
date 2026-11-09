"""Optional strict CSRF validation for multipart form uploads.

FastAPI parses multipart request bodies on its route Request (and caches the
result). This dependency runs before any endpoint mutation and can inspect the
form token without reading a multipart stream in HTTP middleware.

Report-only remains the default. Secondary mounted routes and administrator
session forms have their own mandatory signed CSRF protections.
"""
from __future__ import annotations

import os

from fastapi import HTTPException, Request

from . import session_auth385
from .csrf_reporting import UNSAFE_METHODS
from .csrf_runtime import COOKIE_NAME, FIELD_NAME, HEADER_NAME, load_key
from .csrf_tokens import verify_pair


# Session routes already validate their own signed token/cookie pair.
# The global double-submit cookie must not interfere with their tokens.
SIGNED_SESSION_POST_PATHS520 = frozenset({
    "/login",
    "/logout",
    "/account/password",
    "/account/sessions/revoke-others",
    "/account/users",
    "/account/users/edit",
})


def owns_signed_csrf520(request: Request) -> bool:
    return (
        request.method.upper() == "POST"
        and request.url.path in SIGNED_SESSION_POST_PATHS520
        and session_auth385.enabled()
    )


def strict_csrf_enabled520() -> bool:
    return os.environ.get("TRACKER_CSRF_ENFORCE", "0") == "1"


def is_multipart520(request: Request) -> bool:
    return (
        request.headers.get("content-type", "")
        .split(";", 1)[0].strip().lower()
        == "multipart/form-data"
    )


def _verify_pair520(cookie: str | None, submitted: object) -> None:
    if not cookie or not isinstance(submitted, str):
        raise HTTPException(403, "CSRF token required.")
    try:
        key = load_key()
    except (OSError, ValueError):
        raise HTTPException(503, "CSRF signing key unavailable.") from None
    if not verify_pair(cookie, submitted, key):
        raise HTTPException(403, "CSRF token required.")


async def enforce_multipart_csrf520(request: Request) -> None:
    """Verify multipart writes under strict mode or a proxy-mismatch exception.

    Normal report-only requests remain unparsed by this dependency. Proxy
    mismatch requests specifically flagged by HTTP middleware must pass the
    same mandatory signed token verification before any endpoint can write.

    A valid CSRF request header is sufficient for JS/HTMX uploads. Traditional
    multipart HTML forms without a header must supply exactly one signed form
    field, matching the cookie. We use Request.form() only inside the route,
    where the parser's cached FormData remains available to the endpoint.
    """
    if (
        not (
            strict_csrf_enabled520()
            or getattr(request.state, "proxy_origin_csrf_required522", False)
        )
        or request.method.upper() not in UNSAFE_METHODS
        or owns_signed_csrf520(request)
        or not is_multipart520(request)
    ):
        return

    cookie = request.cookies.get(COOKIE_NAME)
    headers = request.headers.getlist(HEADER_NAME)
    if headers:
        if len(headers) != 1:
            raise HTTPException(403, "CSRF token required.")
        _verify_pair520(cookie, headers[0])
    else:
        # Never call .body() on multipart in HTTP middleware. FastAPI caches
        # the form after normal route parsing; files remain owned by the route.
        form = await request.form()
        tokens = form.getlist(FIELD_NAME)
        if len(tokens) != 1:
            raise HTTPException(403, "CSRF token required.")
        _verify_pair520(cookie, tokens[0])

    request.state.csrf_multipart_verified520 = True
