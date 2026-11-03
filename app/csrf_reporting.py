"""CSRF reporting without enforcement.

Small URL-encoded form submissions are inspected using the
cached request body. Multipart uploads and oversized or
streamed bodies remain uninspected. No tokens, payloads,
or credentials are logged.
"""

from urllib.parse import parse_qsl

from .csrf_runtime import (
    COOKIE_NAME,
    HEADER_NAME,
    FIELD_NAME,
    load_key,
)
from .csrf_tokens import verify_pair

UNSAFE_METHODS = frozenset({
    "POST", "PUT", "PATCH", "DELETE",
})

REPORT_HEADER = "X-Tracker-CSRF-Report"

FORM_TYPES = frozenset({
    "application/x-www-form-urlencoded",
    "multipart/form-data",
})


MAX_INSPECT_BYTES = 64 * 1024


def _verify(cookie, submitted):
    if not submitted or not cookie:
        return "missing"

    try:
        secret = load_key()
        return (
            "valid"
            if verify_pair(cookie, submitted, secret)
            else "invalid"
        )
    except (OSError, ValueError):
        return "unavailable"


async def report_status(request):
    """Report CSRF status; never reject the write request."""
    if request.method.upper() not in UNSAFE_METHODS:
        return None

    content_type = request.headers.get(
        "content-type", ""
    ).split(";", 1)[0].strip().lower()

    submitted = request.headers.get(HEADER_NAME)
    cookie = request.cookies.get(COOKIE_NAME)

    # A header takes precedence. Do not read or alter the body.
    if submitted:
        return _verify(cookie, submitted)

    if content_type == "application/x-www-form-urlencoded":
        # Avoid reading unbounded request streams in middleware.
        length = request.headers.get("content-length", "")
        try:
            size = int(length)
        except ValueError:
            return "form-uninspected"

        if size < 0 or size > MAX_INSPECT_BYTES:
            return "form-uninspected"

        try:
            # Starlette caches request.body(), allowing call_next
            # to receive the original payload unchanged.
            body = await request.body()
            if len(body) > MAX_INSPECT_BYTES:
                return "form-uninspected"

            text = body.decode("utf-8", errors="strict")
            fields = parse_qsl(
                text,
                keep_blank_values=True,
                strict_parsing=False,
                max_num_fields=1024,
                errors="strict",
            )
        except (UnicodeError, ValueError):
            return "invalid"

        tokens = [
            value for key, value in fields
            if key == FIELD_NAME
        ]

        if len(tokens) > 1:
            return "invalid"

        return _verify(
            cookie,
            tokens[0] if tokens else None,
        )

    if content_type == "multipart/form-data":
        # Do not parse multipart in HTTP middleware:
        # files and streams must remain owned by endpoints.
        return "form-uninspected"

    return "missing"
