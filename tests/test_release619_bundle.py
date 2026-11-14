"""Release 617–619 bundled read-only search/workflow/security invariants."""
from pathlib import Path

from fastapi.testclient import TestClient
from jinja2 import Environment

from app.main import app
from app.db import Base, SessionLocal, engine
from app.models import Page
from scripts.tracker_dependency_baseline569 import (
    BASELINE, CONSTRAINTS, read_manifest, read_constraints, validate_constraints,
)

ROOT = Path(__file__).resolve().parents[1]


def test_617_notes_views_compose_with_existing_search():
    Base.metadata.create_all(bind=engine)
    from uuid import uuid4
    marker = "qa619-" + uuid4().hex[:12]
    with SessionLocal() as db:
        sourced = Page(title=marker + " sourced", body="test", tags="qa")
        unsourced = Page(title=marker + " unsourced", body="test", tags="qa")
        db.add_all([sourced, unsourced])
        db.flush()
        # Source association is an existing Notes model, not a new schema.
        from app.models import Source
        db.add(Source(page_id=sourced.id, kind="book", title="QA reference"))
        db.commit()

    with TestClient(app) as client:
        all_view = client.get("/pages", params={"q": marker, "view": "all"})
        assert all_view.status_code == 200
        assert marker + " sourced" in all_view.text
        assert marker + " unsourced" in all_view.text
        with_sources = client.get("/pages", params={"q": marker, "view": "with-sources"})
        assert with_sources.status_code == 200
        assert marker + " sourced" in with_sources.text
        assert marker + " unsourced" not in with_sources.text
        without_sources = client.get("/pages", params={"q": marker, "view": "without-sources"})
        assert without_sources.status_code == 200
        assert marker + " sourced" not in without_sources.text
        assert marker + " unsourced" in without_sources.text
        invalid = client.get("/pages", params={"q": marker, "view": "bogus"})
        assert invalid.status_code == 200
        assert marker + " sourced" in invalid.text
        assert marker + " unsourced" in invalid.text


def test_618_guides_are_read_only_and_original_forms_remain():
    for path, form_marker, guide_marker in (
        ("purchases.html", 'id="new-purchase"', 'id="purchase-review-guide618"'),
        ("blends.html", 'id="blend-form"', 'id="blend-review-guide618"'),
        ("protocols.html", 'action="/protocols"', 'id="protocol-review-guide618"'),
    ):
        source = (ROOT / "app/templates" / path).read_text()
        Environment().parse(source)
        assert guide_marker in source
        assert form_marker in source
        guide = source.split(guide_marker, 1)[1].split("</details>", 1)[0]
        assert "<form" not in guide
        assert "type=\"submit\"" not in guide


def test_619_security_policy_and_observed_dependency_pins_are_unchanged():
    main = (ROOT / "app/main.py").read_text()
    assert 'os.environ.get("TRACKER_CSRF_ENFORCE", "0")' in main
    baseline = read_manifest(BASELINE)
    constraints = read_constraints(CONSTRAINTS)
    validate_constraints(baseline, constraints)
    assert (ROOT / "tests/browser/test_strict_csrf521.py").is_file()
    assert (ROOT / "tests/browser/test_csrf_dose_lifecycle582.py").is_file()
