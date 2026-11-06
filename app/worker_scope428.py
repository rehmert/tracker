"""Offline isolated-worker plan. Never activates an account or opens HTTP."""

import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

from .user_accounts427 import (
    inspect_staged_account427,
    secondary_id,
    staging_environment,
)
from .user_storage388 import planned_storage

SOURCE_ROOT = Path(__file__).resolve().parents[1]


def worker_plan428(user_id, data_root=None):
    uid = secondary_id(user_id)
    root = staging_environment(data_root)
    account = inspect_staged_account427(uid, root)

    if (
        account["credential_status"] != "disabled"
        or account["workspace_status"] != "inactive"
        or account["login_enabled"]
        or account["live_data_access_enabled"]
    ):
        raise PermissionError(
            "Only inactive accounts may be probed"
        )

    private = planned_storage(uid, root)
    admin = planned_storage(1, root)

    if (
        private.root != root / "users" / str(uid)
        or private.database == admin.database
        or private.coa == admin.coa
        or private.labs == admin.labs
        or private.backups == admin.backups
    ):
        raise RuntimeError("Workspace paths are not isolated")

    return private


def worker_environment428(user_id, data_root=None):
    private = worker_plan428(user_id, data_root)

    # Never inherit administrator credentials or Tracker settings.
    environment = {
        key: os.environ[key]
        for key in ("PATH", "LANG", "LC_ALL", "TMPDIR")
        if key in os.environ
    }

    environment.update({
        "PYTHONPATH": str(SOURCE_ROOT),
        "TRACKER_INSTANCE": "DEV",
        "TRACKER_DATA_DIR": str(private.root),
        "TRACKER_BACKUP_DIR": str(private.backups),
        "TRACKER_USER": "isolated-worker",
        "TRACKER_PASS": secrets.token_urlsafe(48),
        "TRACKER_ORIGIN_GUARD": "1",
        "TRACKER_CSRF_ENFORCE": "1",
        "TRACKER_WORKER_USER_ID": str(private.user_id),
        "TRACKER_WORKER_PARENT_DATA_DIR": str(
            private.root.parent.parent
        ),
        "TRACKER_WORKER_PROBE_ONLY": "1",
    })

    return environment


def run_worker_probe428(user_id, data_root=None):
    uid = secondary_id(user_id)
    environment = worker_environment428(uid, data_root)

    result = subprocess.run(
        [sys.executable, "-m", "app.worker_probe428"],
        cwd=SOURCE_ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )

    if result.returncode:
        raise RuntimeError(
            "Offline worker failed (exit "
            + str(result.returncode)
            + "): "
            + result.stderr[-1400:]
        )

    try:
        report = json.loads(result.stdout)
    except (TypeError, ValueError) as error:
        raise RuntimeError(
            "Invalid worker JSON status"
        ) from error

    if (
        report.get("user_id") != uid
        or report.get("mode") != "offline-isolated-probe"
        or report.get("storage_isolated") is not True
        or report.get("feature_routes_verified") != 3
        or report.get("http_listener_started") is not False
        or report.get("account_login_enabled") is not False
    ):
        raise RuntimeError("Worker isolation contract failed")

    return report
