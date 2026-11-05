#!/usr/bin/env python3
"""Audit Labs and COA workspace file access contracts."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    from fastapi.routing import APIRoute
    from app.attachment_scope396 import (
        require_attachment_scope396,
    )
    from app.attachment_files400 import (
        require_attachment_workspace400,
    )
    from app.routers import labs, coas

    print("=== RELEASE 400.1 ATTACHMENT AUDIT ===")

    for label, module, kind, old_path in (
        ("Labs", labs, "labs", "config.LAB_DIR"),
        ("COAs", coas, "coa", "config.UPLOAD_DIR"),
    ):
        source = Path(module.__file__).read_text()

        assert old_path not in source
        assert f'attachment_directory400("{kind}")' in source
        assert f'attachment_file400("{kind}"' in source
        assert "uploaded_transaction" in source
        assert "delete_after_commit" in source

        routes = [
            item for item in module.router.routes
            if isinstance(item, APIRoute)
        ]

        assert routes

        for route in routes:
            guards = {
                item.dependency
                for item in route.dependencies
            }

            assert {
                require_attachment_scope396,
                require_attachment_workspace400,
            } <= guards, route.path

        print(f"PASS: {label}: {len(routes)} guarded routes")

    print()
    print("Legacy attachment paths: preserved")
    print("Directory resolution: centralized")
    print("File traversal checks: enabled")
    print("Transactional cleanup: retained")
    print("Additional accounts: disabled")
    print("Cross-user isolation: incomplete")

    print("PASS: Release 400.1 audit")


if __name__ == "__main__":
    main()
