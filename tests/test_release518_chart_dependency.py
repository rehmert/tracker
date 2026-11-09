"""Release 518: in-range marker query semantics and read-only dependency inventory.

All chart fixtures use isolated, disposable in-memory SQLite.
"""
from datetime import date, datetime, timedelta
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import services
from app.db import Base
from app.models import Compound, DoseLog, LabReport, Purchase, Vial


def _marker(event):
    return (event.kind, event.mark, event.at, event.label)


def test_518_chart_events_skip_out_of_window_records():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    start = datetime(2026, 11, 7, 14)
    end = datetime(2026, 11, 8, 23, 59)
    with Session(engine) as db:
        compound = Compound(name="Chart fixture 518")
        active = Vial(
            compound=compound, content_value=10, content_unit="mg",
            reconstituted_on=date(2026, 11, 7), status="finished",
            label="Active 518",
        )
        old = Vial(
            compound=compound, content_value=10, content_unit="mg",
            reconstituted_on=date(2025, 1, 1), status="finished",
            label="Old 518",
        )
        recent = Vial(
            compound=compound, content_value=10, content_unit="mg",
            reconstituted_on=date(2025, 1, 1), status="finished",
            label="Recent 518",
        )
        new = Vial(
            compound=compound, content_value=10, content_unit="mg",
            reconstituted_on=date(2026, 11, 8), status="sealed",
            label="Reconstituted 518",
        )
        doses = [
            DoseLog(vial=active, taken_at=datetime(2026, 11, 7, 16),
                    entered_value=1, entered_unit="mg", amount_base=1000, kind="dose"),
            DoseLog(vial=active, taken_at=datetime(2026, 11, 8, 10),
                    entered_value=1, entered_unit="mg", amount_base=1000, kind="dose"),
            DoseLog(vial=old, taken_at=datetime(2025, 1, 4),
                    entered_value=1, entered_unit="mg", amount_base=1000, kind="dose"),
            DoseLog(vial=recent, taken_at=datetime(2025, 1, 4),
                    entered_value=1, entered_unit="mg", amount_base=1000, kind="dose"),
            DoseLog(vial=recent, taken_at=datetime(2026, 11, 7, 18),
                    entered_value=1, entered_unit="mg", amount_base=1000, kind="dose"),
        ]
        db.add_all([
            *doses, new,
            Purchase(vendor="Today 518", purchased_on=date(2026, 11, 8)),
            Purchase(vendor="Old 518", purchased_on=date(2025, 1, 1)),
            LabReport(drawn_on=date(2026, 11, 8), lab_name="Lab 518"),
            LabReport(drawn_on=date(2025, 1, 1), lab_name="Old lab 518"),
        ])
        db.commit()
        db.expunge_all()

        sql = []

        def track_sql(conn, cursor, statement, parameters, context, executemany):
            sql.append(statement)

        event.listen(engine, "before_cursor_execute", track_sql)
        try:
            events = services.events_between(db, start, end)
        finally:
            event.remove(engine, "before_cursor_execute", track_sql)

        markers = {_marker(e) for e in events if e.kind == "marker"}
        assert ("marker", "S", datetime(2026, 11, 7, 16),
                "Chart fixture 518 Active 518") in markers
        assert ("marker", "F", datetime(2026, 11, 8, 10),
                "Chart fixture 518 Active 518") in markers
        assert ("marker", "F", datetime(2026, 11, 7, 18),
                "Chart fixture 518 Recent 518") in markers
        assert ("marker", "R", datetime(2026, 11, 8, 12),
                "Chart fixture 518 Reconstituted 518") in markers
        assert not any("Old 518" in e.label or "Old lab" in e.label for e in events)
        assert not any(e.mark == "R" and "Active" in e.label for e in events)
        assert any(e.mark == "P" and "Today" in e.label for e in events)
        assert any(e.mark == "L" and "Lab 518" in e.label for e in events)
        assert sum(e.kind == "dose" for e in events) == 3
        # In-range WHERE clauses are enforced by SQL, not solely Python.
        statements = "\n".join(sql).lower()
        assert "purchases.purchased_on between" in statements
        assert "lab_reports.drawn_on between" in statements
        assert "vials.reconstituted_on between" in statements

    engine.dispose()


def _dependency_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "tracker-dependency-snapshot.py"
    spec = importlib.util.spec_from_file_location("tracker_dependency_snapshot518", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_518_dependency_inventory_redacts_sensitive_runtime_context(tmp_path):
    tool = _dependency_module()
    (tmp_path / "requirements.txt").write_text("fastapi>=0.115\n")
    (tmp_path / "requirements-dev.txt").write_text("pytest>=8\n")
    report = tool.snapshot(tmp_path)
    assert report["schema"] == 1
    assert len(report["requirements_sha256"]["requirements.txt"]) == 64
    assert "fastapi" in report["packages"]
    assert "python_version" in report
    assert "environment" not in report
    assert "paths" not in report
    assert "credentials" not in report


def test_518_dependency_diff_identifies_changed_versions_without_noise():
    tool = _dependency_module()
    first = {
        "packages": {"fastapi": "0.1", "sqlalchemy": "2.0"},
        "requirements_sha256": {"requirements.txt": "abc"},
        "python_version": "3.13.0",
        "python_implementation": "CPython",
        "captured_utc": "yesterday",
    }
    second = {
        "packages": {"fastapi": "0.2", "sqlalchemy": "2.0"},
        "requirements_sha256": {"requirements.txt": "abc"},
        "python_version": "3.13.0",
        "python_implementation": "CPython",
        "captured_utc": "today",
    }
    assert tool.compare_snapshots(first, second) == {
        "packages.fastapi": ["0.1", "0.2"],
    }
