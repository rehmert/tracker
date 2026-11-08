#!/usr/bin/env python3
"""Read-only effective Tracker host security review.

No credentials, environment values, or secret file
contents are printed or stored in reports.
"""

import argparse
import json
import os
import re
import stat
import subprocess
from pathlib import Path


def finding(level, code, message):
    return {
        "level": level,
        "code": code,
        "message": message,
    }


def env_flags(path):
    """Read only presence of authentication settings."""
    keys = {"TRACKER_USER": [], "TRACKER_PASS": []}

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        match = re.match(
            r"^(?:export\s+)?"
            r"(TRACKER_USER|TRACKER_PASS)\s*=(.*)$",
            line,
        )
        if match:
            raw_value = match.group(2).strip()
            # Do not return or log the actual value.
            if (
                len(raw_value) >= 2
                and raw_value[0] == raw_value[-1]
                and raw_value[0] in ("'", '"')
            ):
                raw_value = raw_value[1:-1]

            keys[match.group(1)].append(
                bool(raw_value)
            )

    return keys


def assess(env_path, exec_start, service_user):
    findings = []
    env_path = Path(env_path)

    if not env_path.is_file():
        return [
            finding(
                "FAIL",
                "env_missing",
                "Tracker environment file is missing.",
            )
        ]

    metadata = env_path.stat()
    mode = stat.S_IMODE(metadata.st_mode)

    if mode & 0o077:
        findings.append(finding(
            "FAIL",
            "env_permissions",
            "Environment file is readable or writable "
            "by group or other users.",
        ))
    else:
        findings.append(finding(
            "PASS",
            "env_permissions",
            "Environment file permissions restrict "
            "group and other access.",
        ))

    try:
        flags = env_flags(env_path)
    except (OSError, UnicodeError):
        return findings + [
            finding(
                "FAIL",
                "env_unreadable",
                "Unable to inspect authentication flags.",
            )
        ]

    user_set = flags["TRACKER_USER"]
    pass_set = flags["TRACKER_PASS"]

    if len(user_set) > 1 or len(pass_set) > 1:
        findings.append(finding(
            "FAIL",
            "duplicate_auth_settings",
            "Repeated authentication assignments "
            "require manual review.",
        ))

    has_user = bool(user_set and user_set[-1])
    has_pass = bool(pass_set and pass_set[-1])

    if has_user and has_pass:
        findings.append(finding(
            "PASS",
            "basic_auth_configured",
            "Both HTTP Basic authentication "
            "settings are populated.",
        ))
    elif has_user or has_pass:
        findings.append(finding(
            "FAIL",
            "partial_auth_configuration",
            "Only one authentication setting is populated; "
            "Tracker returns HTTP 503 (fail closed).",
        ))
    else:
        findings.append(finding(
            "WARN",
            "basic_auth_disabled",
            "Both authentication settings are absent "
            "or empty; Tracker allows unauthenticated access.",
        ))

    command = exec_start or ""
    all_interfaces = bool(re.search(
        r"(?:--host(?:=|\s+))"
        r"(?:0\.0\.0\.0|::)(?:\s|$)",
        command,
    ))

    loopback = bool(re.search(
        r"(?:--host(?:=|\s+))"
        r"(?:127\.0\.0\.1|localhost|::1)(?:\s|$)",
        command,
    ))

    if all_interfaces:
        findings.append(finding(
            "WARN",
            "all_interface_bind",
            "Uvicorn is configured to bind to all interfaces. "
            "Verify firewall, reverse proxy, and TLS protections.",
        ))
    elif loopback:
        findings.append(finding(
            "PASS",
            "loopback_bind",
            "Uvicorn is configured for a loopback binding.",
        ))
    else:
        findings.append(finding(
            "WARN",
            "unknown_bind",
            "Unable to determine the effective listening "
            "address from the service command.",
        ))

    if (service_user or "").strip() in ("", "root"):
        findings.append(finding(
            "FAIL",
            "privileged_service",
            "Tracker service appears configured to run as root.",
        ))
    else:
        findings.append(finding(
            "PASS",
            "unprivileged_service",
            "Tracker service has a non-root account.",
        ))

    if all_interfaces and not (has_user and has_pass):
        findings.append(finding(
            "FAIL",
            "exposure_without_basic_auth",
            "All-interface binding combined with disabled "
            "Basic auth requires immediate access review.",
        ))

    return findings


def systemd_property(service, prop):
    result = subprocess.run(
        [
            "systemctl", "show", service,
            "--property", prop, "--value",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"Unable to inspect systemd property: {prop}"
        )
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path("/etc/tracker.env"),
    )
    parser.add_argument(
        "--service",
        default="tracker",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit nonzero for findings requiring review.",
    )
    args = parser.parse_args()

    try:
        # systemctl reports the loaded effective unit,
        # including drop-ins rather than only the
        # repository's example service file.
        command = systemd_property(
            args.service, "ExecStart"
        )
        user = systemd_property(
            args.service, "User"
        )
        findings = assess(
            args.env_file,
            command,
            user,
        )
    except (RuntimeError, OSError) as exc:
        # Avoid dumping subprocess outputs or config values.
        findings = [
            finding(
                "FAIL",
                "inspection_failed",
                "Unable to inspect effective service settings: "
                + type(exc).__name__,
            )
        ]

    for item in findings:
        print(
            item["level"]
            + ": "
            + item["code"]
            + ": "
            + item["message"]
        )

    counts = {
        level: sum(
            f["level"] == level for f in findings
        )
        for level in ("PASS", "WARN", "FAIL")
    }

    print(
        "SUMMARY: "
        + ", ".join(
            f"{level}={count}"
            for level, count in counts.items()
        )
    )

    if args.json is not None:
        args.json.parent.mkdir(
            parents=True, exist_ok=True
        )
        args.json.write_text(
            json.dumps({
                "findings": findings,
                "counts": counts,
            }, indent=2) + "\n",
            encoding="utf-8",
        )

    return (
        1
        if args.strict
        and (counts["FAIL"] or counts["WARN"])
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
