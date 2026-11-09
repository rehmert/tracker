"""DEV-only, explicitly enabled unified secondary login.

Secondary credentials create secondary sessions only.
They never authorize administrator routes or the
administrator's global SQLAlchemy engine.
"""
import os

from .instance_parity523 import interactive_parity523
from . import config, session_auth385


def enabled473():
    from .secondary_preview430 import preview_enabled

    return (
        interactive_parity523()
        and session_auth385.enabled()
        and preview_enabled()
        and os.getenv(
            "TRACKER_MULTIUSER_LOGIN473", "0"
        ) == "1"
    )


def authenticate_secondary473(username, password):
    if not enabled473():
        return None

    from .secondary_preview430 import (
        _verify_credentials,
        _new_session,
    )

    uid = _verify_credentials(username, password)

    if type(uid) is not int or uid <= 1:
        return None

    return uid, _new_session(uid)
