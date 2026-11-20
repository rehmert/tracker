"""Release 711 source contracts: correct one existing physical draw, never vial stock."""
from __future__ import annotations

import ast
from pathlib import Path
import subprocess

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_711_all_touched_python_and_shell_scripts_parse():
    for path in (
        "app/routers/doses.py",
        "app/routers/blends.py",
        "app/blend_dose_identity711.py",
        "app/manual_supplies.py",
        "tests/test_release711_blend_dose_corrections.py",
        "tests/browser/test_blend_corrections711.py",
    ):
        ast.parse(source(path), filename=path)
    for path in (
        "scripts/tracker-release.sh",
        "scripts/tracker-browser-qualify.sh",
        "scripts/tracker-release-scoped711.sh",
        "scripts/tracker-qualify711.sh",
        "scripts/tracker-install711.sh",
        "scripts/tracker_prod_remote568.sh",
    ):
        subprocess.run(["bash", "-n", str(ROOT / path)], check=True)


def test_711_correction_routes_are_physical_blend_only_and_audited():
    router = source("app/routers/doses.py")
    assert '@router.get("/doses/blends/{did}/edit")' in router
    assert '@router.post("/doses/blends/{did}/edit")' in router
    assert '@router.post("/doses/blends/{did}/delete")' in router
    assert "def _blend_dose_snapshot711(" in router
    assert "def _blend_corrected_plan711(" in router
    assert 'view = SimpleNamespace(' in router
    assert 'status="in_use"' in router
    assert 'draw.blend.status = (' in router
    assert 'if kind not in ("dose", "waste"):' in router
    assert 'if site and site not in INJECTION_SITES:' in router
    assert "selected = await manual_supplies.selections(request, db, credits=credits)" in router
    assert 'manual_supplies.restore_blend_dose(db, did)' in router
    assert 'manual_supplies.deduct(db, selected, blend_dose_id=did)' in router
    assert 'record(db, "blend_dose", did, "edit"' in router
    assert 'record(db, "blend_dose", did, "delete"' in router
    assert "require_inventory_write(db)" in router
    assert "reserve_inventory_write(db)" in router
    assert 'if confirm_delete != "yes":' in router
    assert 'db.delete(draw)' in router
    assert 'db.commit()' in router
    # All Release 711 logic starts after the preexisting DoseLog routes.
    r711 = router.split("# Release 711:", 1)[1]
    assert "db.add(DoseLog(" not in r711
    assert "draw.blend_id =" not in r711
    assert "source_vial" not in r711

    supplies = source("app/manual_supplies.py")
    assert "def restore_blend_dose(db, did):" in supplies
    assert "SupplyUsage.blend_dose_id == did" in supplies
    assert "item.remaining_qty += usage.amount" in supplies


def test_711_correction_exposed_from_both_histories_and_blend_detail():
    doses = source("app/templates/doses.html")
    detail = source("app/templates/blend_detail.html")
    edit = source("app/templates/blend_dose_edit711.html")
    assert 'href="/doses/blends/{{ r.draw.id }}/edit"' in doses
    assert 'href="/doses/blends/{{ row.draw.id }}/edit"' in doses
    assert 'href="/doses/blends/{{ dose.id }}/edit"' in detail
    assert 'action="/doses/blends/{{ dose.id }}/edit"' in edit
    assert 'action="/doses/blends/{{ dose.id }}/delete"' in edit
    assert 'id="tracker-dose-correction-form"' in edit
    assert 'name="confirm_delete" value="yes" required' in edit
    assert 'id="tracker-dose-correction-review"' in edit
    assert 'data-original="{{ used.get(s.id, 0) }}"' in edit
    assert 'data-available="{{ s.remaining_qty + used.get(s.id, 0) }}"' in edit
    assert "event.before_json | from_json" in edit
    assert "event.after_json | from_json" in edit
    assert "dose.entered_value if dose.entered_value is not none" in edit
    for name in ("app/templates/doses.html", "app/templates/blend_detail.html",
                 "app/templates/blend_dose_edit711.html"):
        Environment().parse(source(name))


def test_711_strict_browser_is_tracked_only_in_disposable_modes():
    index = source("tests/test_browser_qualification511.py")
    qualifier = source("scripts/tracker-browser-qualify.sh")
    assert '"tests/browser/test_blend_corrections711.py"' in index
    assert '("blend-correction711", "TARGETED_711_BLEND_CORRECTION_DELETE=PASSED")' in index
    assert qualifier.count("tests/browser/test_blend_corrections711.py") == 2
    assert "TARGETED_711_BLEND_CORRECTION_DELETE=PASSED" in qualifier
    assert "STRICT_711_BLEND_CORRECTION_DELETE=PASSED" in qualifier
    assert 'TRACKER_CSRF_ENFORCE=1' in qualifier
    script = source("scripts/tracker-qualify711.sh")
    assert "PrivateNetwork=yes required" in script
    assert "Clean installed Release 710 required" in script
    assert "scripts/tracker-impact-preflight604.py" in script
    assert "RELEASE_711_INSTALLED_DEV=UNMODIFIED" in script
    deploy = source("scripts/tracker-release.sh")
    assert "RELEASE_711_PROD_SCOPED=PASSED" in deploy
    assert "scripts/tracker-release-scoped711.sh" in deploy
    assert "--db-migration" not in source("scripts/tracker-install711.sh")
