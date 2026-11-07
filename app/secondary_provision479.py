"""DEV-only secondary account provisioning.

Intended to run as the tracker service identity.
Never alter existing workspaces or administrator records.
"""
import json
import os
import stat
import sys
from pathlib import Path

from . import config, session_auth385 as auth
from .user_accounts427 import (
    list_staged_accounts427,
    stage_secondary_account427,
    validate_password,
    validate_username,
)
from .user_bootstrap426 import initialize_staged_workspace426


def create_secondary_user479(username, password, confirmation):
    if config.instance_label() != "DEV" or not auth.enabled():
        raise PermissionError("DEV session authentication required")

    username = validate_username(username)
    password = validate_password(password)

    if password != confirmation:
        raise ValueError("Passwords do not match")

    accounts = list_staged_accounts427()

    if any(
        a["username"].casefold() == username.casefold()
        for a in accounts
    ):
        raise FileExistsError("Username already exists")

    root = Path(config.DATA_DIR)
    users = root / "users"

    if users.is_symlink():
        raise ValueError("Symlinked user directory forbidden")

    if users.exists():
        if not users.is_dir():
            raise ValueError("Invalid user directory")

        # A service account must be able to create future
        # private workspaces without using root privileges.
        if (
            users.stat().st_uid != os.geteuid()
            or not os.access(users, os.W_OK | os.X_OK)
        ):
            raise PermissionError(
                "User storage must be owned by service identity"
            )

    existing = {a["user_id"] for a in accounts}
    uid = 2

    while uid < 2147483647:
        path = users / str(uid)
        if (
            uid not in existing
            and not path.exists()
            and not path.is_symlink()
        ):
            break
        uid += 1
    else:
        raise RuntimeError("No available secondary account ID")

    paths = initialize_staged_workspace426(uid, root)

    # Verify ownership BEFORE writing credentials. On failure
    # the new workspace stays inactive for manual inspection.
    for path in (
        paths.root,
        paths.database,
        paths.coa,
        paths.labs,
        paths.backups,
    ):
        info = path.lstat()

        if info.st_uid != os.geteuid():
            raise PermissionError(
                "Private workspace owner mismatch"
            )

        if not (
            stat.S_ISDIR(info.st_mode)
            or stat.S_ISREG(info.st_mode)
        ):
            raise PermissionError(
                "Invalid private workspace file type"
            )

    record = stage_secondary_account427(
        uid, username, password, root
    )

    return {
        "user_id": record["user_id"],
        "username": record["username"],
        "workspace": str(paths.root),
    }


def main():
    # A root caller must switch to tracker before invoking
    # this entry point. Never let root own new user files.
    if os.geteuid() == 0:
        raise SystemExit(
            "ERROR: Provisioning must run as tracker, not root"
        )

    payload = json.load(sys.stdin)

    if set(payload) != {
        "username", "password", "confirmation"
    }:
        raise SystemExit("ERROR: Invalid provisioning input")

    result = create_secondary_user479(
        payload["username"],
        payload["password"],
        payload["confirmation"],
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
