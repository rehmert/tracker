#!/usr/bin/env python3
"""Guarded, reversible PROD opt-in to the same interactive login as DEV.

Run as root ONLY after Release 523 has passed DEV and been installed in PROD.
The PROD administrator password is migrated from the current local Basic Auth
configuration without printing it or placing it in command-line arguments.
No DEV data or credentials are ever copied.
"""
from __future__ import annotations

import argparse
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path("/opt/tracker")
ENV = Path("/etc/tracker.env")
OVERRIDE = Path("/etc/tracker-parity523.env")
DROPIN_DIR = Path("/etc/systemd/system/tracker.service.d")
DROPIN = DROPIN_DIR / "90-tracker-parity523.conf"
MARKER = ".tracker-session-auth-prod523"
FLAGS = (
    "TRACKER_PROD_PARITY523",
    "TRACKER_SECONDARY_PREVIEW430",
    "TRACKER_MULTIUSER_LOGIN473",
    "TRACKER_SECONDARY_VITAL_WRITES433",
    "TRACKER_SECONDARY_DOSE_WRITES434",
    "TRACKER_SECONDARY_INVENTORY_WRITES435",
    "TRACKER_SECONDARY_FOOD_WRITES456",
    "TRACKER_SECONDARY_SUPPLY_WRITES438",
    "TRACKER_SECONDARY_SUPPLY_USE439",
    "TRACKER_SECONDARY_RECONSTITUTION_WRITES436",
    "TRACKER_SECONDARY_VIAL_CORRECTIONS437",
    "TRACKER_SECONDARY_ATTACHMENT_UPLOAD472",
)


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def settings():
    if ENV.is_symlink() or not ENV.is_file():
        raise RuntimeError("Unexpected /etc/tracker.env configuration")
    values = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, raw = (v.strip() for v in line.split("=", 1))
        if key not in (
            "TRACKER_INSTANCE", "TRACKER_USER", "TRACKER_PASS",
            "TRACKER_DATA_DIR",
        ):
            continue
        fields = shlex.split(raw, comments=False)
        if len(fields) != 1:
            raise RuntimeError("Invalid " + key + " configuration")
        if key in values:
            raise RuntimeError("Repeated " + key + " configuration")
        values[key] = fields[0]
    if values.get("TRACKER_INSTANCE", "").upper() != "PROD":
        raise RuntimeError("Refusing activation outside PROD")
    if not values.get("TRACKER_USER") or not values.get("TRACKER_PASS"):
        raise RuntimeError("Existing PROD Basic Auth credentials required")
    root = Path(values.get("TRACKER_DATA_DIR") or ROOT / "data").resolve()
    if not root.is_dir() or root.is_symlink():
        raise RuntimeError("Missing or symlinked PROD data directory")
    db = root / "tracker.db"
    if db.is_symlink() or not db.is_file():
        raise RuntimeError("Missing PROD primary SQLite database")
    return values, root, db


def process_env():
    pid = run("systemctl", "show", "tracker.service", "-p", "MainPID", "--value")
    if not pid.isdecimal() or int(pid) <= 1:
        raise RuntimeError("Tracker is not running")
    env = {}
    for item in Path(f"/proc/{pid}/environ").read_bytes().split(b"\x00"):
        if b"=" in item:
            key, value = item.split(b"=", 1)
            env[key.decode(errors="replace")] = value.decode(errors="replace")
    return env


def check_process(ready):
    env = process_env()
    if env.get("TRACKER_INSTANCE") != "PROD":
        raise RuntimeError("Running Tracker process is not PROD")
    if ready:
        bad = [key for key in FLAGS if env.get(key) != "1"]
        if env.get("TRACKER_SECONDARY_LOCKDOWN440") == "1":
            bad.append("TRACKER_SECONDARY_LOCKDOWN440")
        if bad:
            raise RuntimeError("Live parity feature mismatch: " + ", ".join(bad))
    else:
        if env.get("TRACKER_PROD_PARITY523", "0") == "1":
            raise RuntimeError("PROD parity remains enabled in live process")


def verify_login():
    # Direct loopback request, avoiding cookies, passwords and proxy settings.
    # Verify that an unauthenticated browser sees the login page rather than
    # Basic Auth. Session-aware sidebar smoke additionally verifies all pages.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "tracker_smoke523", ROOT / "scripts/tracker-runtime-smoke.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    port = module.port_from_service()
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), module.NoRedirect()
    )
    def get(path):
        try:
            with opener.open(
                urllib.request.Request(
                    f"http://127.0.0.1:{port}{path}",
                    headers={"User-Agent": "Tracker-Parity523-Check"},
                ), timeout=8,
            ) as response:
                return response.status, response.headers, response.read(100_000)
        except urllib.error.HTTPError as error:
            return error.code, error.headers, error.read(100_000)

    code, headers, _ = get("/")
    if code != 303 or not headers.get("location", "").startswith("/login"):
        raise RuntimeError("Unauthenticated PROD root did not redirect to login")
    code, _, body = get("/login")
    if code != 200 or b'name="csrf_token"' not in body:
        raise RuntimeError("PROD browser login is unavailable")
    subprocess.run([
        sys.executable, str(ROOT / "scripts/tracker-runtime-smoke.py"),
        "--instance", "PROD",
    ], check=True)


def prepare_auth(values, data, db):
    os.environ.update({
        "TRACKER_INSTANCE": "PROD",
        "TRACKER_PROD_PARITY523": "1",
        "TRACKER_DATA_DIR": str(data),
    })
    sys.path.insert(0, str(ROOT))
    from app import session_auth385 as auth

    store = data / auth.DATABASE
    marker = data / auth.PROD_FLAG523
    if store.is_symlink() or marker.is_symlink():
        raise RuntimeError("Unexpected auth database or marker symlink")
    if marker.exists():
        raise RuntimeError("PROD session login already activated")

    created = False
    if not store.exists():
        auth.bootstrap(values["TRACKER_USER"], values["TRACKER_PASS"])
        created = True

    # Verify we can authenticate with the existing PROD password before
    # replacing Basic Auth. Never display the password.
    if not auth.verify_admin(values["TRACKER_USER"], values["TRACKER_PASS"]):
        raise RuntimeError("Existing PROD credentials do not match auth store")
    if store.stat().st_mode & 0o077:
        raise RuntimeError("Unsafe session authentication database permissions")

    owner = db.stat()
    for file in (store, data / (auth.DATABASE + "-wal"), data / (auth.DATABASE + "-shm")):
        if file.exists():
            if file.is_symlink():
                raise RuntimeError("Unexpected auth sidecar symlink")
            os.chown(file, owner.st_uid, owner.st_gid)
            os.chmod(file, 0o600)
    return marker, owner.st_uid, owner.st_gid


def atomic_text(path, content, mode):
    if path.exists() or path.is_symlink():
        raise RuntimeError("Refusing to overwrite existing " + str(path))
    fd, temp = tempfile.mkstemp(prefix=".parity523-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def activate():
    if os.geteuid() != 0:
        raise RuntimeError("Root required")
    if run("git", "-C", str(ROOT), "branch", "--show-current") != "main":
        raise RuntimeError("PROD checkout must be main")
    if run("git", "-C", str(ROOT), "status", "--porcelain"):
        raise RuntimeError("Dirty PROD source checkout")
    if run("systemctl", "is-active", "tracker.service") != "active":
        raise RuntimeError("Tracker service must be active")
    values, data, db = settings()
    check_process(False)
    if OVERRIDE.exists() or OVERRIDE.is_symlink():
        raise RuntimeError("Parity configuration already installed")
    if DROPIN.exists() or DROPIN.is_symlink() or DROPIN_DIR.is_symlink():
        raise RuntimeError("Unexpected parity drop-in state")
    marker, uid, gid = prepare_auth(values, data, db)

    # The authentication store is now usable; until the marker and opt-in
    # service environment are both set, the application retains Basic Auth.
    DROPIN_DIR.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        atomic_text(OVERRIDE, "".join(f"{k}=1\n" for k in FLAGS), 0o644)
        created.append(OVERRIDE)
        atomic_text(
            DROPIN,
            "[Service]\nEnvironmentFile=/etc/tracker-parity523.env\n",
            0o644,
        )
        created.append(DROPIN)
        fd = os.open(
            marker,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        os.close(fd)
        os.chown(marker, uid, gid)
        created.append(marker)
        run("systemctl", "daemon-reload")
        run("systemctl", "restart", "tracker.service")
        check_process(True)
        verify_login()
    except BaseException:
        # Atomic fallback restores previous Basic Auth if any check fails.
        # The securely stored but inactive auth database is retained.
        for file in reversed(created):
            file.unlink(missing_ok=True)
        subprocess.run(["systemctl", "daemon-reload"], check=False)
        subprocess.run(["systemctl", "restart", "tracker.service"], check=False)
        print("ROLLBACK: PROD session activation cancelled; Basic Auth restored")
        raise
    print("PROD_LOGIN_PARITY523=ENABLED")
    print("PROD_BASIC_AUTH_REPLACED=YES")
    print("PROD_PRIVATE_USER_ROUTES=ENABLED")
    print("Credentials migrated from existing PROD Basic Auth; no DEV data copied")


def status():
    values, data, _ = settings()
    marker = data / MARKER
    print("PROD_SESSION_MARKER=" + ("PRESENT" if marker.is_file() else "ABSENT"))
    print("PROD_PARITY_DROPIN=" + ("PRESENT" if DROPIN.is_file() else "ABSENT"))
    env = process_env()
    print("PROD_LIVE_PARITY=" + (
        "ENABLED" if env.get("TRACKER_PROD_PARITY523") == "1" else "DISABLED"
    ))
    print("PROD_SECONDARY_LOGIN=" + (
        "ENABLED" if env.get("TRACKER_MULTIUSER_LOGIN473") == "1" else "DISABLED"
    ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("enable", "status"))
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit("Root required")
    try:
        if args.command == "enable":
            activate()
        else:
            status()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
