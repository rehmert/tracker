"""Offline subprocess overview for a staged, inactive secondary user."""

import json
import subprocess
import sys

from .worker_read429 import COUNT_TABLES
from .worker_scope428 import SOURCE_ROOT, worker_environment428
from .user_accounts427 import secondary_id


def read_workspace_overview429(user_id, data_root=None):
    uid = secondary_id(user_id)

    environment = worker_environment428(uid, data_root)

    result = subprocess.run(
        [sys.executable, "-m", "app.worker_read429"],
        input='{"action":"overview"}',
        cwd=SOURCE_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )

    if result.returncode:
        raise RuntimeError(
            f"Private worker failed (exit {result.returncode}): "
            + result.stderr[-1000:]
        )

    try:
        report = json.loads(result.stdout)
    except (ValueError, TypeError) as error:
        raise RuntimeError("Worker returned invalid JSON") from error

    if (
        type(report) is not dict
        or report.get("mode") != "offline-readonly-worker"
        or report.get("user_id") != uid
        or report.get("workspace_status") != "inactive"
        or report.get("http_listener_started") is not False
        or report.get("login_enabled") is not False
    ):
        raise RuntimeError("Private worker identity contract failed")

    counts = report.get("counts")

    if (
        type(counts) is not dict
        or set(counts) != set(COUNT_TABLES)
        or any(
            type(x) is not int or x < 0
            for x in counts.values()
        )
    ):
        raise RuntimeError("Private worker counts invalid")

    return report
