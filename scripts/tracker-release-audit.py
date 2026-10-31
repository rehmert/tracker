#!/usr/bin/env python3
"""
Tracker Release Audit — Stages 34.65–34.72

Read-only checks:
  34.65  Static asset integrity
  34.66  Duplicate asset references
  34.67  JavaScript syntax
  34.68  Jinja template integrity
  34.69  Accessibility indicators
  34.70  Repository hygiene
  34.71  JSON release report
  34.72  Release readiness summary

No database access or application writes.
"""

import argparse
import collections
import datetime
import html.parser
import json
import pathlib
import re
import subprocess
import sys
import urllib.parse

from jinja2 import Environment

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app/templates"
STATIC = ROOT / "app/static"



class HTMLScan(html.parser.HTMLParser):
    """HTML scanner with nested-label awareness."""

    def __init__(self):
        super().__init__(convert_charrefs=True)

        self.assets = []
        self.ids = []
        self.labels = set()
        self.controls = []
        self.images = []
        self.buttons = []
        self.tables = 0
        self.forms = 0

        self._label_depth = 0
        self._label_stack = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)

        if tag == "label":
            self._label_depth += 1
            self._label_stack.append(True)

            if attributes.get("for"):
                self.labels.add(attributes["for"])

        if "id" in attributes:
            self.ids.append(attributes["id"])

        if tag in ("script", "link", "img"):
            asset = (
                attributes.get("src")
                or attributes.get("href")
            )

            if asset:
                self.assets.append(asset)

        if tag == "img":
            self.images.append(attributes)

        if tag in ("input", "select", "textarea"):
            control = dict(attributes)

            control["_wrapped_label"] = (
                self._label_depth > 0
            )

            control["_line"] = self.getpos()[0]

            self.controls.append(control)

        if tag == "button":
            self.buttons.append(attributes)

        if tag == "table":
            self.tables += 1

        if tag == "form":
            self.forms += 1

    def handle_endtag(self, tag):
        if tag == "label":
            if self._label_depth:
                self._label_depth -= 1

            if self._label_stack:
                self._label_stack.pop()


class Audit:
    def __init__(self):
        self.failures = []
        self.warnings = []
        self.passes = []
        self.stats = collections.Counter()

    def pass_check(self, message):
        self.passes.append(message)

    def warn(self, message):
        self.warnings.append(message)

    def fail(self, message):
        self.failures.append(message)

    def section(self, title):
        print()
        print("=== " + title + " ===")

    def summarize_section(self, title, before):
        passed = len(self.passes) - before[0]
        warned = len(self.warnings) - before[1]
        failed = len(self.failures) - before[2]

        print(
            f"{title}: "
            f"{passed} passed, "
            f"{warned} warnings, "
            f"{failed} failures"
        )


def snapshot(audit):
    return (
        len(audit.passes),
        len(audit.warnings),
        len(audit.failures),
    )


def is_dynamic(value):
    return (
        "{{" in value or
        "{%" in value or
        "${" in value
    )


def audit_templates(audit):
    audit.section("34.68: Template Integrity")
    before = snapshot(audit)

    environment = Environment(
        extensions=["jinja2.ext.do"]
    )

    templates = sorted(
        TEMPLATES.rglob("*.html")
    )

    audit.stats["templates"] = len(templates)

    if not templates:
        audit.fail("No HTML templates found")

    for path in templates:
        relative = path.relative_to(ROOT)

        try:
            source = path.read_text(
                encoding="utf-8"
            )

            environment.parse(source)

            audit.pass_check(
                f"Jinja: {relative}"
            )

        except Exception as exc:
            audit.fail(
                f"Jinja: {relative}: {exc}"
            )

    audit.summarize_section(
        "Templates",
        before
    )

    return templates


def audit_assets(audit, templates):
    audit.section("34.65–34.66: Asset Integrity")
    before = snapshot(audit)

    references = collections.defaultdict(list)
    scans = {}

    for path in templates:
        relative = str(
            path.relative_to(ROOT)
        )

        try:
            source = path.read_text(
                encoding="utf-8"
            )
        except Exception:
            continue

        scanner = HTMLScan()

        try:
            scanner.feed(source)
        except Exception as exc:
            audit.warn(
                f"{relative}: HTML scan error: {exc}"
            )
            continue

        scans[relative] = scanner

        for asset in scanner.assets:
            if is_dynamic(asset):
                continue

            parsed = urllib.parse.urlsplit(
                asset
            )

            if not parsed.path.startswith(
                "/static/"
            ):
                continue

            name = parsed.path[len("/static/"):]

            if not name:
                continue

            references[name].append(relative)

            candidate = (
                STATIC / name
            ).resolve()

            try:
                candidate.relative_to(
                    STATIC.resolve()
                )
            except ValueError:
                audit.fail(
                    f"Asset path escapes static directory: "
                    f"{asset}"
                )
                continue

            if candidate.is_file():
                audit.pass_check(
                    f"Asset: {name}"
                )
            else:
                audit.fail(
                    f"Missing asset: {name} "
                    f"(referenced by {relative})"
                )

    audit.stats["asset_references"] = sum(
        len(items)
        for items in references.values()
    )

    audit.stats["unique_assets"] = len(
        references
    )

    for name, files in references.items():
        counts = collections.Counter(files)

        for filename, count in counts.items():
            if count > 1:
                audit.warn(
                    f"Repeated asset reference: "
                    f"{name} in {filename} "
                    f"({count} occurrences)"
                )

    audit.summarize_section(
        "Assets",
        before
    )

    return scans


def audit_javascript(audit):
    audit.section("34.67: JavaScript Syntax")
    before = snapshot(audit)

    files = sorted(
        STATIC.rglob("*.js")
    )

    audit.stats["javascript_files"] = len(
        files
    )

    for path in files:
        relative = path.relative_to(ROOT)

        try:
            result = subprocess.run(
                [
                    "node",
                    "--check",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )

        except Exception as exc:
            audit.fail(
                f"JS check {relative}: {exc}"
            )
            continue

        if result.returncode == 0:
            audit.pass_check(
                f"JS: {relative}"
            )
        else:
            audit.fail(
                f"JS: {relative}: "
                f"{result.stderr.strip()[:300]}"
            )

    audit.summarize_section(
        "JavaScript",
        before
    )



def audit_accessibility(audit, scans):
    audit.section("34.69: Accessibility Indicators")
    before = snapshot(audit)

    reviewed = 0
    unlabeled = []

    for filename, scan in scans.items():
        ids = [
            value
            for value in scan.ids
            if not is_dynamic(value)
        ]

        duplicates = [
            key
            for key, count in
            collections.Counter(ids).items()
            if count > 1
        ]

        for identifier in duplicates:
            audit.warn(
                f"{filename}: repeated literal ID "
                f"{identifier!r}"
            )

        for image in scan.images:
            if "alt" not in image:
                audit.warn(
                    f"{filename}: image without alt "
                    "attribute"
                )

        for control in scan.controls:
            field_type = (
                control.get("type") or ""
            ).lower()

            if field_type in (
                "hidden",
                "submit",
                "button",
                "reset",
                "image",
            ):
                continue

            reviewed += 1

            identifier = control.get("id")

            has_name = bool(
                control.get("_wrapped_label")
                or control.get("aria-label")
                or control.get("aria-labelledby")
                or control.get("title")
            )

            if (
                identifier
                and not is_dynamic(identifier)
                and identifier in scan.labels
            ):
                has_name = True

            if not has_name:
                line = control.get("_line", "?")

                description = (
                    control.get("name")
                    or identifier
                    or "<unnamed>"
                )

                unlabeled.append(
                    f"{filename}:{line}: "
                    f"control {description!r} "
                    "needs label review"
                )

        audit.stats["forms"] += scan.forms
        audit.stats["tables"] += scan.tables

    audit.stats["controls_reviewed"] = reviewed
    audit.stats["controls_needing_label_review"] = (
        len(unlabeled)
    )

    for message in unlabeled:
        audit.warn(message)

    audit.pass_check(
        f"Accessibility scan completed: "
        f"{reviewed} controls reviewed"
    )

    audit.summarize_section(
        "Accessibility",
        before
    )


def audit_repository(audit):
    audit.section("34.70: Repository Hygiene")
    before = snapshot(audit)

    result = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "ls-files",
            "-z",
        ],
        capture_output=True,
        check=False,
    )

    if result.returncode:
        audit.fail(
            "Could not enumerate tracked Git files"
        )
        return

    tracked = [
        item.decode(
            "utf-8",
            errors="replace"
        )
        for item in result.stdout.split(b"\0")
        if item
    ]

    audit.stats["tracked_files"] = len(
        tracked
    )

    dangerous_names = {
        ".env",
        ".env.local",
        "id_rsa",
        "id_ed25519",
        "credentials.json",
        "service-account.json",
    }

    dangerous_suffixes = (
        ".pem",
        ".key",
        ".p12",
        ".pfx",
    )

    database_suffixes = (
        ".sqlite",
        ".sqlite3",
        ".db",
    )

    for filename in tracked:
        path = pathlib.PurePosixPath(
            filename
        )

        name = path.name.lower()

        if (
            name in dangerous_names or
            name.endswith(dangerous_suffixes)
        ):
            audit.warn(
                "Potential sensitive file tracked: "
                + filename
            )

        if name.endswith(database_suffixes):
            audit.warn(
                "Database file tracked: "
                + filename
            )

        if (
            "backup" in path.parts or
            "backups" in path.parts
        ):
            audit.warn(
                "Backup directory content tracked: "
                + filename
            )

    audit.pass_check(
        "Tracked-file hygiene scan completed"
    )

    audit.summarize_section(
        "Repository",
        before
    )


def audit_integrations(audit):
    audit.section("34.63–34.64: UX Integration Review")
    before = snapshot(audit)

    base = TEMPLATES / "base.html"

    if not base.exists():
        audit.fail(
            "Shared base template missing"
        )
        return

    source = base.read_text(
        encoding="utf-8"
    )

    expected = [
        "tracker-ux-3447-3452.js",
        "tracker-ux-3453-3458.js",
    ]

    for asset in expected:
        count = source.count(asset)

        if count == 1:
            audit.pass_check(
                f"UX integration: {asset}"
            )
        elif count == 0:
            audit.warn(
                f"UX integration absent: {asset}"
            )
        else:
            audit.warn(
                f"UX integration duplicated: "
                f"{asset} ({count})"
            )

    audit.summarize_section(
        "UX Integration",
        before
    )


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--json",
        dest="json_path",
        help="Write JSON report"
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures"
    )

    args = parser.parse_args()

    audit = Audit()

    print("Tracker Release Audit")
    print("Repository:", ROOT)
    print(
        "UTC:",
        datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
    )

    templates = audit_templates(audit)

    scans = audit_assets(
        audit,
        templates
    )

    audit_javascript(audit)

    audit_accessibility(
        audit,
        scans
    )

    audit_repository(audit)

    audit_integrations(audit)

    report = {
        "generated_at": (
            datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()
        ),
        "repository": str(ROOT),
        "stats": dict(audit.stats),
        "passed_checks": len(audit.passes),
        "warnings": audit.warnings,
        "failures": audit.failures,
        "ready": (
            not audit.failures and
            (
                not args.strict or
                not audit.warnings
            )
        ),
    }

    print()
    print("================================")
    print(" Release Readiness Summary")
    print("================================")

    for key, value in sorted(
        audit.stats.items()
    ):
        print(f"{key}: {value}")

    print()
    print("Passed checks:", len(audit.passes))
    print("Warnings:", len(audit.warnings))
    print("Failures:", len(audit.failures))

    if audit.warnings:
        print()
        print("=== Warnings ===")

        for warning in audit.warnings:
            print("WARN:", warning)

    if audit.failures:
        print()
        print("=== Failures ===")

        for failure in audit.failures:
            print("FAIL:", failure)

    if args.json_path:
        target = pathlib.Path(
            args.json_path
        ).expanduser()

        target.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        target.write_text(
            json.dumps(
                report,
                indent=2
            ) + "\n",
            encoding="utf-8"
        )

        print()
        print("JSON report:", target)

    print()
    print(
        "RESULT:",
        "PASS" if report["ready"] else "FAIL"
    )

    return 0 if report["ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
