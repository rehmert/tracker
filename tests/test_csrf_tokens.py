"""Cryptographic CSRF token foundation tests."""

import base64
import secrets

import pytest

from app.csrf_tokens import (
    issue_token,
    verify_pair,
    verify_token,
)

KEY = bytes(range(32))
OTHER_KEY = bytes(range(32, 64))


def test_token_round_trip():
    token = issue_token(KEY)

    assert token.startswith("v1.")
    assert verify_token(token, KEY)
    assert verify_pair(token, token, KEY)


def test_each_token_is_random():
    tokens = {issue_token(KEY) for _ in range(100)}

    assert len(tokens) == 100


def test_key_isolation():
    token = issue_token(KEY)

    assert not verify_token(token, OTHER_KEY)
    assert not verify_pair(token, token, OTHER_KEY)


def test_tampered_signature():
    token = issue_token(KEY)
    parts = token.split(".")

    changed = (
        "0" if parts[2][0] != "0" else "1"
    )
    parts[2] = changed + parts[2][1:]

    assert not verify_token(".".join(parts), KEY)


def test_tampered_nonce():
    token = issue_token(KEY)
    parts = token.split(".")

    changed = (
        "A" if parts[1][0] != "A" else "B"
    )
    parts[1] = changed + parts[1][1:]

    assert not verify_token(".".join(parts), KEY)


def test_cookie_submission_mismatch():
    first = issue_token(KEY)
    second = issue_token(KEY)

    assert not verify_pair(first, second, KEY)
    assert verify_pair(first, first, KEY)


@pytest.mark.parametrize(
    "bad",
    [
        None,
        "",
        "v1",
        "v2." + "A" * 43 + "." + "0" * 64,
        "v1." + "A" * 43,
        "v1." + "A" * 43 + "." + "G" * 64,
        "v1." + "A" * 43 + "." + "0" * 63,
        "v1." + "A" * 43 + "." + "0" * 65,
        "v1." + "A" * 43 + "." + "0" * 64 + "\n",
        "<script>alert(1)</script>",
        123,
        b"not-a-token",
    ],
)
def test_invalid_tokens_rejected(bad):
    assert not verify_token(bad, KEY)


def test_missing_pair_rejected():
    token = issue_token(KEY)

    assert not verify_pair(None, token, KEY)
    assert not verify_pair(token, None, KEY)
    assert not verify_pair("", token, KEY)
    assert not verify_pair(token, "", KEY)


@pytest.mark.parametrize(
    "weak",
    [
        b"",
        b"short",
        b"x" * 31,
        "string-is-not-a-byte-key",
        None,
    ],
)
def test_weak_secrets_fail_closed(weak):
    with pytest.raises(ValueError):
        issue_token(weak)

    with pytest.raises(ValueError):
        verify_token("anything", weak)

    with pytest.raises(ValueError):
        verify_pair("a", "a", weak)


def test_key_length_32_and_longer():
    assert verify_token(
        issue_token(b"x" * 32),
        b"x" * 32,
    )

    assert verify_token(
        issue_token(b"x" * 64),
        b"x" * 64,
    )


def test_base64_noncanonical_nonce_rejected():
    token = issue_token(KEY)
    parts = token.split(".")

    raw = base64.urlsafe_b64decode(
        parts[1] + "="
    )
    assert len(raw) == 32

    # An extra character must never be accepted.
    parts[1] += "A"
    assert not verify_token(".".join(parts), KEY)


def test_secret_not_embedded_in_token():
    key = secrets.token_bytes(32)
    token = issue_token(key)

    assert key.hex() not in token
    assert verify_token(token, key)
