#!/usr/bin/env python3
"""Release 418: read-only inventory of known background storage entry points.

Classifications describe source-level evidence, not runtime authorization.
This tool never imports the application or runs any maintenance operation.
It does not inspect installed cron jobs, timers, or host configuration.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Expected markers come from the reviewed Release 417 source.
# A changed marker requires a fresh classification review.
TARGETS = {
    "scheduled_backup": (
        "scripts/tracker_backup.py",
        "admin_context_default",
        (
            "context = administrator_context410()",
            "data_dir=context.data_dir",
            "verify_restorable(archive)",
            "removed = prune_backups(",
        ),
    ),
    "replication_cli": (
        "scripts/tracker_replica.py",
        "validated_default_manual_override",
        (
            "if args.source is None:",
            "administrator_replication_context413(",
            "result = replicate(",
            'parser.add_argument("--source", type=Path, default=None)',
        ),
    ),
    "maintenance_cli": (
        "scripts/tracker_db_maintenance.py",
        "opt_in_scoped_legacy_available",
        (
            "--admin-scoped",
            "scoped_paths416(",
            "publish_verified_snapshot417(",
            "result = snapshot(",
        ),
    ),
    "legacy_shell_backup": (
        "scripts/backup.sh",
        "legacy_unscoped_write",
        (
            "TRACKER_DATA_DIR",
            'sqlite3 "$DATA/tracker.db"',
            "tar -czf",
            'mkdir -p "$OUT"',
        ),
    ),
    "database_health_sweep": (
        "scripts/check_database_health.py",
        "broad_discovery_read_only",
        (
            "SEARCH_PATHS",
            'directory.rglob("*.db")',
            "sqlite3.connect(",
        ),
    ),
    "database_upgrade": (
        "scripts/tracker-db-upgrade.sh",
        "unscoped_migration_write",
        (
            "python -m alembic",
            "upgrade head",
        ),
    ),
    "restore_verifier": (
        "scripts/tracker-restore-verify.py",
        "read_only_optional_receipt_write",
        (
            "--record-status",
            "restore_check(args.archive",
            "record_restore(args.archive, stats)",
        ),
    ),
    "source_preflight": (
        "scripts/tracker-preflight.py",
        "source_snapshot_optional_write",
        (
            "--snapshot",
            'BACKUPS = pathlib.Path("/tmp/tracker-backups")',
            "destination.mkdir(",
        ),
    ),
    "replication_wrapper": (
        "scripts/replicate_backups.sh",
        "delegate_to_replication_cli",
        (
            'tracker_replica.py "$@"',
        ),
    ),
    "backup_timer_unit": (
        "deploy/tracker-backup.service",
        "configured_backup_entrypoint",
        (
            "User=tracker",
            "-m scripts.tracker_backup create",
        ),
    ),
    "backup_library": (
        "app/backup.py",
        "library_with_global_defaults",
        (
            "def create_backup(",
            "data_dir or config.DATA_DIR",
            "backup_dir or BACKUP_DIR",
            "def prune_backups(",
        ),
    ),
    "release_backup": (
        "scripts/tracker-release.sh",
        "release_guard_verified_archive",
        (
            "=== Verified source and data recovery backup ===",
            "create_backup(Path(sys.argv[1]),Path(sys.argv[2]))",
            "=== ISOLATED RESTORE VERIFICATION PASSED ===",
        ),
    ),
}

# Informational review candidates, not confirmed vulnerabilities.
REVIEW_REQUIRED = {
    "validated_default_manual_override",
    "opt_in_scoped_legacy_available",
    "legacy_unscoped_write",
    "broad_discovery_read_only",
    "unscoped_migration_write",
    "read_only_optional_receipt_write",
    "source_snapshot_optional_write",
    "library_with_global_defaults",
}


def source_inventory(root=ROOT):
    items = {}

    for name, (relative, classification, markers) in TARGETS.items():
        path = root / relative
        source = path.read_text(encoding="utf-8")

        if path.suffix == ".py":
            ast.parse(source, filename=relative)

        evidence = {}

        for marker in markers:
            for line, content in enumerate(source.splitlines(), 1):
                if marker in content:
                    evidence[marker] = line
                    break
            else:
                raise RuntimeError(
                    "Source changed; review classification: "
                    f"{relative}: {marker}"
                )

        items[name] = {
            "path": relative,
            "classification": classification,
            "requires_review": classification in REVIEW_REQUIRED,
            "sha256": hashlib.sha256(
                source.encode("utf-8")
            ).hexdigest(),
            "evidence_lines": evidence,
        }

    return items


def build_report(root=ROOT):
    items = source_inventory(root)

    return {
        "release": 418,
        "scope": (
            "curated source-only inventory; "
            "live jobs not inspected"
        ),
        "multi_user_enabled": False,
        "background_job_isolation_complete": False,
        "additional_accounts_allowed": False,
        "entrypoints": items,
        "review_queue": sorted(
            name
            for name, item in items.items()
            if item["requires_review"]
        ),
        "next_action": (
            "Audit whether legacy shell backup, broad database sweep, "
            "and unscoped CLI modes are scheduled or callable in production"
        ),
    }


def validate(report):
    if set(report["entrypoints"]) != set(TARGETS):
        raise RuntimeError(
            "Background inventory coverage changed"
        )

    if any(
        report[flag]
        for flag in (
            "multi_user_enabled",
            "background_job_isolation_complete",
            "additional_accounts_allowed",
        )
    ):
        raise RuntimeError(
            "Unexpected isolation-complete claim"
        )

    expected_queue = sorted(
        name
        for name, item in report["entrypoints"].items()
        if item["requires_review"]
    )

    if report["review_queue"] != expected_queue:
        raise RuntimeError(
            "Review queue does not match source inventory"
        )

    if "legacy_shell_backup" not in report["review_queue"]:
        raise RuntimeError(
            "Legacy backup review was lost"
        )

    if "database_health_sweep" not in report["review_queue"]:
        raise RuntimeError(
            "Database sweep review was lost"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_report()
    validate(report)

    if args.json:
        print(json.dumps(
            report,
            indent=2,
            sort_keys=True,
        ))
        return 0

    print("=== RELEASE 418 BACKGROUND ENTRYPOINT AUDIT ===")

    for name, item in report["entrypoints"].items():
        status = (
            "REVIEW"
            if item["requires_review"]
            else "INVENTORIED"
        )
        print(
            f"{status}: {name}: "
            f"{item['classification']} "
            f"({item['path']})"
        )

    print(
        f"Review candidates: "
        f"{len(report['review_queue'])}"
    )
    print("Runtime scheduling: not inspected")
    print("Background isolation: INCOMPLETE")
    print("Secondary accounts: DISABLED")
    print("PASS: Read-only source audit completed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
