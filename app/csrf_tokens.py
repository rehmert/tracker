"""Signed CSRF double-submit token primitives.

This module does not install middleware or enforce CSRF policy.

A later integration must use a secret shared by every worker
on the same instance, deliver a host-bound browser cookie,
and require a matching token in a form field or request header.

Tokens are intentionally opaque and contain no user records.
"""

import base64
import hashlib
import hmac
import re
import secrets

_VERSION = "v1"
_CONTEXT = b"tracker-csrf-v1\x00"
_PATTERN = re.compile(
    r"v1\.([A-Za-z0-9_-]{43})\.([0-9a-f]{64})\Z",
    re.ASCII,
)


def _key(secret):
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise ValueError(
            "CSRF signing secret must be at least 32 bytes"
        )
    return secret


def _signature(secret, nonce):
    return hmac.new(
        _key(secret),
        _CONTEXT + nonce,
        hashlib.sha256,
    ).hexdigest()


def issue_token(secret):
    """Create an unpredictable, signed version-1 token."""
    key = _key(secret)
    nonce = secrets.token_bytes(32)
    value = base64.urlsafe_b64encode(
        nonce
    ).decode("ascii").rstrip("=")

    return (
        f"{_VERSION}.{value}."
        f"{_signature(key, nonce)}"
    )


def verify_token(token, secret):
    """Return False for any missing or malformed token."""
    key = _key(secret)

    if not isinstance(token, str):
        return False

    match = _PATTERN.fullmatch(token)
    if match is None:
        return False

    encoded, provided = match.groups()

    try:
        nonce = base64.b64decode(
            encoded + "=",
            altchars=b"-_",
            validate=True,
        )
    except (ValueError, base64.binascii.Error):
        return False

    if len(nonce) != 32:
        return False

    # Reject noncanonical alternative base64 encodings.
    canonical = base64.urlsafe_b64encode(
        nonce
    ).decode("ascii").rstrip("=")

    if not hmac.compare_digest(canonical, encoded):
        return False

    expected = _signature(key, nonce)
    return hmac.compare_digest(expected, provided)


def verify_pair(cookie_token, submitted_token, secret):
    """Verify both the signed cookie and exact submitted value.

    Accept only a pair matching a signature produced with the
    application's trusted signing secret.
    """
    key = _key(secret)

    if not isinstance(cookie_token, str):
        return False

    if not isinstance(submitted_token, str):
        return False

    if not verify_token(cookie_token, key):
        return False

    return hmac.compare_digest(
        cookie_token,
        submitted_token,
    )
