#!/usr/bin/env python3
"""Release 639 reviewed additive schema guard: one new facts table only."""
import argparse
import ast
import subprocess
from pathlib import Path

ALLOWED = frozenset({
    "app/models.py",
    "app/routers/regimen635.py",
    "app/routers/regimen_catalog636.py",
    "app/static/js/tracker-regimen-catalog636.js",
    "app/static/js/tracker-regimen-facts639.js",
    "app/templates/regimen635.html",
    "scripts/tracker-release.sh",
    "scripts/tracker_prod_remote568.sh",
    "scripts/tracker-browser-qualify.sh",
    "tests/test_release635_schema_review.py",
    "scripts/tracker_csrf_runtime_report579.py",
    "tests/test_release640_csrf_inventory.py",
    "tests/test_release575_csrf_js_review.py",
    "tests/test_release576_csrf_js_triage.py",
    "tests/test_release578_csrf_route_ledger.py",
    "tests/test_release579_csrf_runtime_report.py",
    "scripts/tracker_schema_review639.py",
    "scripts/tracker-regimen-facts-live639.py",
    "docs/release-639-structured-supplement-facts.md",
    "tests/test_release639_supplement_facts.py",
    "tests/test_release639_schema_review.py",
    "tests/browser/test_regimen_facts639_ui.py",
    "tests/test_release636_regimen_catalog.py",
    "tests/browser/test_regimen_catalog638_ui.py",
})


def git(root, *args):
    p = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
        text=True, capture_output=True, check=False,
    )
    if p.returncode:
        raise ValueError(p.stderr[:300])
    return p.stdout


# PROD's pre-639 main can still be at Release 635. The schema delta
# must be inspected against immutable, DEV-qualified Release 638, while the
# existing database/model prefix is checked against PROD's actual baseline.
PROD_635_BASE = "1e938154ee4315873c968b4661bbd0953701c1e1"
DEV_638_BASE = "94bf84d61410bb9cf9be2bc150f0e8f6114e83a2"


def review(root, base, target):
    review_base = base
    if base == PROD_635_BASE:
        # An exact historical ancestry check prevents importing unknown
        # changes as part of the reviewed 639 schema delta.
        git(root, "merge-base", "--is-ancestor", base, DEV_638_BASE)
        git(root, "merge-base", "--is-ancestor", DEV_638_BASE, target)
        base_models = git(root, "show", f"{base}:app/models.py")
        dev_models = git(root, "show", f"{DEV_638_BASE}:app/models.py")
        if not dev_models.startswith(base_models):
            raise ValueError("Historical existing model definitions changed")
        legacy = ast.parse(dev_models[len(base_models):])
        legacy_classes = [
            node.name for node in legacy.body
            if isinstance(node, ast.ClassDef)
        ]
        if (legacy_classes !=
                ["RegimenItem", "RegimenSchedule", "RegimenEntry"] or
                len(legacy.body) != 3):
            raise ValueError("Unexpected pre-639 regimen schema delta")
        review_base = DEV_638_BASE

    changed = set(git(root, "diff", "--name-only", review_base, target).splitlines())
    if not changed or not changed <= ALLOWED:
        raise ValueError("Unreviewed Release 639 paths: " +
                         ", ".join(sorted(changed - ALLOWED)))
    if "app/models.py" not in changed:
        raise ValueError("Expected append-only facts table missing")
    old = git(root, "show", f"{review_base}:app/models.py")
    new = git(root, "show", f"{target}:app/models.py")
    if not new.startswith(old):
        raise ValueError("Existing model source modified")
    extra = ast.parse(new[len(old):])
    if len(extra.body) != 1 or not isinstance(extra.body[0], ast.ClassDef):
        raise ValueError("Only one appended model class allowed")
    model = extra.body[0]
    if model.name != "RegimenProductFacts639":
        raise ValueError("Unexpected model class")
    tables = [
        node.value.value for node in model.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "__tablename__"
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ]
    if tables != ["regimen_product_facts639"]:
        raise ValueError("Only regimen_product_facts639 may be added")
    if "regimen_product_facts639" in old:
        raise ValueError("Facts table already exists in baseline")
    if changed & {"app/db.py", "app/migrations.py", "requirements.txt"}:
        raise ValueError("Core migration or dependency edits not authorized")
    print("RELEASE_639_APPEND_ONLY_SCHEMA_REVIEW=PASSED")
    print("RELEASE_639_CHANGED_PATHS=", len(changed))
    print("RELEASE_639_REVIEW_BASE=", review_base)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True, type=Path)
    p.add_argument("--base", required=True)
    p.add_argument("--target", required=True)
    args = p.parse_args()
    review(args.root.resolve(), args.base, args.target)
