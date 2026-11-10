#!/usr/bin/env python3
"""Read-only Tracker security configuration inspection.

Does not execute env files, import Tracker, disclose credential values,
connect to any service, or modify files. Nonzero exit on errors;
--fail-on-risk also rejects reported high-risk settings.
"""

import argparse
import os
import shlex
import stat
from pathlib import Path


RELEVANT = frozenset({
    "TRACKER_INSTANCE",
    "TRACKER_DATA_DIR",
    "TRACKER_USER",
    "TRACKER_PASS",
    "TRACKER_CSRF_ENFORCE",
    "TRACKER_ORIGIN_GUARD",
})

DEFAULT_DATA = Path("/opt/tracker/data")


class AuditError(ValueError):
    pass


def parse_env_file(path):
    """Parse relevant literal assignments without shell expansion."""
    if path.is_symlink() or not path.is_file():
        raise AuditError("Environment file missing or symbolic link")

    settings = {}

    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("export "):
            stripped = stripped[7:].strip()

        if "=" not in stripped:
            continue

        name, raw = stripped.split("=", 1)
        name = name.strip()

        if name not in RELEVANT:
            continue

        if name in settings:
            raise AuditError(
                f"Duplicate relevant configuration key at line {number}"
            )

        try:
            fields = shlex.split(raw.strip(), comments=False)
        except ValueError as exc:
            raise AuditError(
                f"Invalid configuration syntax at line {number}"
            ) from exc

        if len(fields) != 1:
            raise AuditError(
                f"Invalid configuration value at line {number}"
            )

        settings[name] = fields[0]

    return settings


def inspect(settings, envfile, expected_instance=None):
    findings = []

    def add(code, severity, detail):
        findings.append((code, severity, detail))

    instance = settings.get(
        "TRACKER_INSTANCE", ""
    ).strip().upper()

    if instance not in ("DEV", "PROD"):
        add(
            "INSTANCE_UNSET",
            "HIGH",
            "DEV or PROD instance identity not configured",
        )
    elif expected_instance and instance != expected_instance:
        add(
            "INSTANCE_MISMATCH",
            "HIGH",
            "Configured instance does not match expected host",
        )
    else:
        add("INSTANCE", "OK", f"{instance} identity configured")

    raw_data = settings.get("TRACKER_DATA_DIR", "").strip()

    if raw_data:
        path = Path(raw_data).expanduser()
        if not path.is_absolute():
            path = Path("/opt/tracker") / path
        data_dir = path.resolve(strict=False)
    else:
        data_dir = DEFAULT_DATA

    user = bool(settings.get("TRACKER_USER"))
    password = bool(settings.get("TRACKER_PASS"))

    if user != password:
        add(
            "PARTIAL_BASIC_AUTH",
            "HIGH",
            "Only one Basic authentication setting is present",
        )

    marker = data_dir / ".tracker-session-auth-dev"
    database = data_dir / "tracker-auth.sqlite3"

    if marker.is_symlink():
        add(
            "SESSION_MARKER_SYMLINK",
            "HIGH",
            "Session activation marker is a symbolic link",
        )
        session_enabled = False
    else:
        session_enabled = (
            instance in ("DEV", "PROD")
            and marker.is_file()
        )

    if session_enabled:
        if database.is_symlink() or not database.is_file():
            add(
                "SESSION_STORE_UNAVAILABLE",
                "HIGH",
                "Session authentication store missing or symbolic link",
            )
        else:
            add(
                "SESSION_AUTH",
                "OK",
                "Session activation marker and store present",
            )
        if user and password:
            add(
                "BASIC_FALLBACK",
                "INFO",
                "Basic credentials configured; session mode takes priority",
            )
    elif user and password:
        add(
            "BASIC_AUTH",
            "OK",
            "Complete Basic authentication settings present",
        )
    else:
        add(
            "NO_AUTH_CONFIG",
            "HIGH",
            "No enabled session marker or complete Basic credentials",
        )

    csrf = settings.get("TRACKER_CSRF_ENFORCE", "0")
    if csrf == "1":
        add("STRICT_CSRF", "OK", "Global CSRF enforcement enabled")
    elif csrf == "0":
        add(
            "CSRF_REPORT_ONLY",
            "WARN",
            "Global CSRF policy uses report-only mode",
        )
    else:
        add(
            "CSRF_INVALID_VALUE",
            "WARN",
            "Unrecognized CSRF setting behaves as report-only",
        )

    origin = settings.get("TRACKER_ORIGIN_GUARD", "1")
    if origin == "0":
        add(
            "ORIGIN_GUARD_DISABLED",
            "HIGH",
            "Cross-origin write guard explicitly disabled",
        )
    elif origin == "1":
        add(
            "ORIGIN_GUARD",
            "OK",
            "Cross-origin write guard enabled",
        )
    else:
        add(
            "ORIGIN_GUARD_NONSTANDARD",
            "WARN",
            "Nonstandard origin setting; application treats it as enabled",
        )

    mode = stat.S_IMODE(envfile.stat().st_mode)
    if mode & 0o077:
        add(
            "ENVFILE_PERMISSIONS",
            "WARN",
            "Environment file has group/other permission bits",
        )
    else:
        add(
            "ENVFILE_PERMISSIONS",
            "OK",
            "Environment file has no group/other permission bits",
        )

    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--envfile",
        type=Path,
        default=Path("/etc/tracker.env"),
    )
    parser.add_argument(
        "--instance",
        choices=("DEV", "PROD"),
    )
    parser.add_argument(
        "--fail-on-risk",
        action="store_true",
        help="Return exit status 2 when HIGH findings exist",
    )
    args = parser.parse_args(argv)

    try:
        settings = parse_env_file(args.envfile)
        findings = inspect(
            settings, args.envfile, args.instance
        )
    except (OSError, UnicodeError, AuditError, ValueError) as exc:
        # Never display file contents or exception values that
        # might contain configuration secrets.
        print("SECURITY_AUDIT=ERROR")
        print("Environment configuration could not be safely inspected")
        return 1

    for code, severity, detail in findings:
        print(f"{severity}: {code}: {detail}")

    high = sum(level == "HIGH" for _, level, _ in findings)
    warnings = sum(level == "WARN" for _, level, _ in findings)

    print(f"HIGH_FINDINGS={high}")
    print(f"WARN_FINDINGS={warnings}")

    if high and args.fail_on_risk:
        print("SECURITY_AUDIT=RISK")
        return 2

    print("SECURITY_AUDIT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
