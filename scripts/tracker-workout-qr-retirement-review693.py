#!/usr/bin/env python3
"""Release 693: exact-scope removal of obsolete Workout QR UI and routes."""
from pathlib import Path
import argparse
import ast
import subprocess

BASE = "696fe7f482436090df5342f76cd65b9fb5febad4"
EXPECTED = frozenset({
    "app/templates/workouts654.html",
    "app/routers/workouts654.py",
    "app/routers/data_quality674.py",
    "app/templates/data_quality674.html",
    "tests/test_workouts654.py",
    "tests/test_workouts656.py",
    "tests/test_workout_no_camera692.py",
    "tests/test_integrated_productivity674.py",
    "tests/test_workout_no_qr693.py",
    "scripts/tracker-workout-qr-retirement-review693.py",
    "scripts/tracker-release-scoped693.sh",
    "scripts/tracker-preview693.sh",
})


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        text=True,
    )


def review(root: Path, base: str, target: str) -> None:
    if base != BASE or git(root, "rev-parse", "HEAD").strip() != target:
        raise ValueError("Release 693 source not the exact expected qualified baseline/target")
    subprocess.run([
        "git", "-c", f"safe.directory={root}", "-C", str(root),
        "merge-base", "--is-ancestor", base, target,
    ], check=True)
    actual = frozenset(git(root, "diff", "--name-only", base, target).splitlines())
    if actual != EXPECTED:
        raise ValueError("Unreviewed Release 693 source delta: " + repr(sorted(actual ^ EXPECTED)))
    protected = ("app/models.py", "app/migrations.py", "app/db.py",
                 "app/workout_models654.py", "app/workout_models655.py",
                 "app/scoped_db390.py", "app/main.py", "app/routers/workouts656.py")
    if git(root, "diff", "--name-only", base, target, "--", *protected).strip():
        raise ValueError("Unexpected schema, auth, or progress route changes")
    if git(root, "diff", "--name-only", "--diff-filter=D", base, target).strip():
        raise ValueError("No source/database files should be deleted in this release")

    template = (root / "app/templates/workouts654.html").read_text(encoding="utf-8")
    for forbidden in ("Find a machine", "Paste a Nautilus QR code", "QR text or URL",
                      'action="/workouts/qr"', 'name="qr_value"', "Setup &amp; QR",
                      "QR code value", "QR code URL/text", "Map QR codes once"):
        if forbidden in template:
            raise ValueError("Obsolete Workout QR interface remains: " + forbidden)
    for required in ("Equipment &amp; Logging", "Add Equipment", "Machine Setup",
                     "Save Settings", "Gym Mode", "Progress &amp; History"):
        if required not in template:
            raise ValueError("Essential Workout UI accidentally removed: " + required)

    route = (root / "app/routers/workouts654.py").read_text(encoding="utf-8")
    ast.parse(route)
    if '@router.get("/workouts/qr")' in route or 'qr_value: str = Form' in route:
        raise ValueError("QR lookup or write interface remains active")
    if "machine.qr_value =" in route or "qr_value=qr" in route:
        raise ValueError("Legacy QR mappings must be preserved and no new QR map created")
    for required in ('@router.post("/workouts/equipment")',
                     '@router.post("/workouts/equipment/{equipment_id}/settings")',
                     '@router.post("/workouts/sets")', 'get_scoped_db390'):
        if required not in route:
            raise ValueError("Critical Workout path missing: " + required)

    quality = (root / "app/routers/data_quality674.py").read_text(encoding="utf-8")
    ast.parse(quality)
    quality_html = (root / "app/templates/data_quality674.html").read_text(encoding="utf-8")
    if "Machine has no QR mapping" in quality or "Equipment &amp; QR Mapping" in quality_html:
        raise ValueError("Retired QR data-quality warning remains")
    if "Workout Equipment" not in quality_html:
        raise ValueError("Workout Equipment navigation was lost")

    # Explicitly keep the normal Gym Mode finder, which searches by name.
    old_quick = git(root, "show", f"{base}:app/templates/workout_quick659.html")
    new_quick = (root / "app/templates/workout_quick659.html").read_text(encoding="utf-8")
    if old_quick != new_quick or "Find Machine" not in new_quick:
        raise ValueError("Name-based Gym Mode machine finder must remain unchanged")
    print("RELEASE_693_QR_RETIREMENT_SOURCE_REVIEW=PASSED")
    print("RELEASE_693_DB_SCHEMA_CHANGE=NONE")
    print("RELEASE_693_GYM_MODE_FINDER=PRESERVED")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    review(args.root.resolve(), args.base, args.target)


if __name__ == "__main__":
    main()
