#!/usr/bin/env python3
"""
Tracker Stage 34.58
Read-only UI regression checks.

Checks:
- Jinja syntax across templates
- Local static asset references
- JavaScript syntax for installed UX batches
- Duplicate IDs within individual templates
- Presence of expected integration markers

Does not start Tracker or modify its database.
"""

from pathlib import Path
from collections import Counter
import re
import subprocess
import sys

from jinja2 import Environment, TemplateSyntaxError

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app/templates"
STATIC = ROOT / "app/static"

failures = []
warnings = []

def fail(message):
    failures.append(message)
    print("FAIL:", message)

def warn(message):
    warnings.append(message)
    print("WARN:", message)

def passed(message):
    print("PASS:", message)

print("=== Tracker UI Regression Checks ===")

templates = sorted(TEMPLATES.rglob("*.html"))

if not templates:
    fail("No Jinja templates found")

environment = Environment(
    extensions=["jinja2.ext.do"]
)

for template in templates:
    relative = template.relative_to(ROOT)

    try:
        source = template.read_text(
            encoding="utf-8"
        )
    except Exception as exc:
        fail(f"{relative}: {exc}")
        continue

    try:
        environment.parse(source)
        passed(f"Jinja: {relative}")
    except TemplateSyntaxError as exc:
        fail(
            f"Jinja: {relative}, "
            f"line {exc.lineno}: {exc.message}"
        )

    # Detect duplicate literal IDs.
    # Dynamic Jinja IDs are excluded.
    ids = re.findall(
        r'\bid\s*=\s*["\']([^"\']+)["\']',
        source
    )

    static_ids = [
        value for value in ids
        if "{{" not in value and "{%" not in value
    ]

    duplicates = [
        value
        for value, count in Counter(static_ids).items()
        if count > 1
    ]

    for value in duplicates:
        warn(
            f"{relative}: repeated literal id={value!r}"
        )

    # Check local assets referenced by literal
    # src/href attributes.
    assets = re.findall(
        r'''(?:src|href)\s*=\s*["'](/static/[^"']+)["']''',
        source
    )

    for asset in assets:
        clean = asset.split("?", 1)[0]
        relative_asset = clean.removeprefix("/static/")
        path = STATIC / relative_asset

        if not path.is_file():
            fail(
                f"{relative}: missing asset {clean}"
            )

print()
print("=== JavaScript Syntax ===")

javascript_files = [
    STATIC / "js/tracker-ux-3447-3452.js",
    STATIC / "js/tracker-ux-3453-3458.js",
    STATIC / "js/tracker-compound-inventory.js",
    STATIC / "js/tracker-inventory-review-tools.js",
    STATIC / "js/tracker-vial-lifecycle.js",
]

for path in javascript_files:
    if not path.exists():
        warn(
            f"Optional JavaScript file absent: "
            f"{path.relative_to(ROOT)}"
        )
        continue

    result = subprocess.run(
        ["node", "--check", str(path)],
        capture_output=True,
        text=True
    )

    if result.returncode:
        fail(
            f"JavaScript: {path.relative_to(ROOT)}\n"
            f"{result.stderr.strip()}"
        )
    else:
        passed(
            f"JavaScript: {path.relative_to(ROOT)}"
        )

print()
print("=== Required Integration ===")

base = TEMPLATES / "base.html"

if base.exists():
    content = base.read_text(encoding="utf-8")

    for marker in (
        "tracker-ux-3447-3452.js",
        "tracker-ux-3453-3458.js",
    ):
        if content.count(marker) == 1:
            passed(f"Integrated: {marker}")
        else:
            fail(
                f"Missing or duplicate integration: {marker}"
            )

print()
print("=== Summary ===")

print("Templates checked:", len(templates))
print("Warnings:", len(warnings))
print("Failures:", len(failures))

if failures:
    print("RESULT: FAILED")
    sys.exit(1)

print("RESULT: PASSED")
