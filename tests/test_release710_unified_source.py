"""Release 710 source contracts for unified dose workflow and safe migration."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_710_python_modules_parse_and_model_preserves_two_physical_sources():
    for name in (
        "app/blend_dose_unified710.py",
        "app/routers/doses.py",
        "app/migrations.py",
        "app/manual_supplies.py",
        "app/models.py",
        "tests/test_release710_unified_blend_dose.py",
        "tests/browser/test_blend_unified_dose710.py",
    ):
        ast.parse(source(name), filename=name)
    logic = source("app/blend_dose_unified710.py")
    assert 'return "vial", int(value)' in logic
    assert 'return "blend", int(value.split(":", 1)[1])' in logic
    assert "rows[component.compound_id]" in logic
    assert "A mixed-compound blend must be logged" in logic
    doses = source("app/routers/doses.py")
    assert 'vial_id: str = Form(...)' in doses
    assert 'source_kind, source_pk = source_identity710(vial_id)' in doses
    assert 'physical = BlendDose(' in doses
    assert 'manual_supplies.deduct(db, selected, blend_dose_id=physical.id)' in doses
    assert 'HX-Redirect": "/doses#dose-history-unified614"' in doses
    assert 'return HTMLResponse("", headers={' in doses
    assert 'source_kind == "blend"' in doses
    assert 'vial = db.get(Vial, source_pk)' in doses
    assert 'db.add(DoseLog(vial_id=source_pk' not in doses
    assert 'record(db, "blend", blend.id, "draw"' in doses


def test_710_one_standard_form_selects_blends_and_keeps_legacy_route():
    template = source("app/templates/doses.html")
    assert template.count('hx-post="/doses"') == 1
    assert 'value="blend:{{ row.blend.id }}"' in template
    assert 'id="dose-blend-picker"' not in template
    assert "{% if vials or active_blends %}" in template
    assert "tracker-dose-source710.js?v=712" in template
    assert 'data-physical-source="blend:{{ r.blend.id }}"' in template
    assert "r.draw.entered_value if r.draw.entered_value is not none" in template
    detail = source("app/templates/blend_detail.html")
    assert 'href="/doses?source=blend:{{ blend.id }}#quick-dose-entry"' in detail
    assert 'action="/blends/{{ blend.id }}/doses"' in detail
    assert "@router.post('/blends/{blend_id}/doses')" in source("app/routers/blends.py")
    assert 'blend:[1-9]' in source("app/static/js/tracker-dose-fast602.js")
    assert "option?.dataset.source === 'blend'" in source("app/static/dose_context.js")


def test_710_switching_physical_sources_cannot_relabel_a_previous_dose():
    script = source("app/static/js/tracker-dose-source710.js")
    assert "let previous = source.value;" in script
    assert "if (source.value === previous) return;" in script
    assert "amount.value = '';" in script
    assert "remaining.checked = false;" in script
    assert "unit.value = 'mL';" in script
    assert "form.addEventListener('reset'" in script


def test_710_new_nullable_blend_fields_and_supply_fk_are_additive():
    models = source("app/models.py")
    migrations = source("app/migrations.py")
    for item in (
        'blend_dose_id: Mapped[int | None]',
        'site: Mapped[str] = mapped_column(String(80), default="", server_default="")',
        'entered_value: Mapped[float | None]',
        'entered_unit: Mapped[str | None]',
    ):
        assert item in models
    for item in (
        'if "blend_doses" in tables:',
        'if "supply_usages" in tables:',
        '"ALTER TABLE blend_doses ADD COLUMN {name} {sql}"',
        "ALTER TABLE supply_usages ADD COLUMN blend_dose_id INTEGER",
        'CREATE INDEX IF NOT EXISTS ix_supply_usages_blend_dose_id',
    ):
        assert item in migrations
    assert 'blend_dose_id=blend_dose_id' in source("app/manual_supplies.py")
    assert "DROP TABLE" not in migrations
    assert "DELETE FROM blend_doses" not in migrations


def test_710_strict_real_browser_is_once_in_full_and_once_targeted():
    runner = source("scripts/tracker-browser-qualify.sh")
    path = "tests/browser/test_blend_unified_dose710.py"
    assert runner.count(path) == 2
    start = runner.index('echo "=== STRICT CSRF CORE TESTS PASSED ==="')
    targeted = runner.index(
        'if [[ "$MODE" == targeted && "$TARGETED_MODULE" == blend-vial710 ]]'
    )
    assert runner[start:targeted].count(path) == 1
    assert 'STRICT_710_UNIFIED_BLEND_VIAL_DOSE=PASSED' in runner
    assert 'TARGETED_710_UNIFIED_BLEND_VIAL_DOSE=PASSED' in runner
    assert 'TARGETED_710_SCOPE=ONE_REAL_PHYSICAL_BLEND_WRITE_NOT_FULL_RELEASE' in runner
    index = source("tests/test_browser_qualification511.py")
    assert '"tests/browser/test_blend_unified_dose710.py"' in index
    assert '("blend-vial710", "TARGETED_710_UNIFIED_BLEND_VIAL_DOSE=PASSED")' in index


def test_710_detached_dev_candidate_only_no_installed_modification():
    worker = source("scripts/tracker-blend-vial710.sh")
    for value in (
        "BASE=4c084ade9063b3b01c2de0a4a055d2e23470b2a3",
        "REF=release/710-unified-blend-vial-dosing",
        'git merge-base --is-ancestor "$BASE" "$TARGET"',
        'git worktree add --detach "$QA" "$TARGET"',
        'git -C "$APP" worktree remove --force "$QA"',
        'readlink /proc/self/ns/net',
        'readlink /proc/1/ns/net',
        "--targeted-strict blend-vial710",
        "RELEASE_710_SOURCE=PASSED",
        "RELEASE_710_UNIFIED_BLEND_BROWSER=PASSED",
    ):
        assert value in worker, value
    for forbidden in (
        "systemctl restart tracker", "ssh ", "git push",
        "/etc/tracker.env", "pip download", "pip install",
    ):
        assert forbidden not in worker


def test_710_guarded_install_scripts_parse_and_keep_schema_approval():
    """Regression: the Release 710 installer must parse BEFORE deploy begins."""
    import subprocess

    for name in (
        "scripts/tracker-install710.sh",
        "scripts/tracker-release.sh",
        "scripts/tracker-release-scoped710.sh",
        "scripts/tracker-blend-vial710.sh",
        "scripts/tracker_prod_remote568.sh",
    ):
        subprocess.run(["bash", "-n", str(ROOT / name)], check=True)
    installer = source("scripts/tracker-install710.sh")
    assert 'EXPECTED_BLOB="$(git rev-parse' in installer
    assert 'ACTUAL_BLOB="$(git hash-object "$RUNNER")"' in installer
    assert '[[ "$ACTUAL_BLOB" == "$EXPECTED_BLOB" ]]' in installer
    assert '--ref "$REF" --db-migration --reviewed-blend-710' in installer
    release = source("scripts/tracker-release.sh")
    assert '"$PY" "$QA/scripts/tracker_schema_review710.py"' in release
    assert 'BLEND_710_SCHEMA_PROCEDURE=AUTHORIZED' in release
    assert 'RELEASE_710_PROD_SCOPED=PASSED' in release
    assert 'REVIEWED_BLEND_710="${20:-0}"' in release
    assert '[[ $# -ge 12 && $# -le 20 ]]' in release
    remote = source("scripts/tracker_prod_remote568.sh")
    assert 'elif [[ "$RELEASE" == 710 ]]; then' in remote
    assert 'DEPLOY_EXTRA=(--reviewed-blend-710 --db-migration)' in remote


def test_710_modified_static_assets_use_fresh_template_urls_before_install():
    base = source("app/templates/base.html")
    doses = source("app/templates/doses.html")
    assert base.count("/static/dose_context.js?v=710") == 1
    assert doses.count("/static/js/tracker-dose-fast602.js?v=710") == 1
    assert "dose_context.js?v=20261030-210017" not in base
    assert "tracker-dose-fast602.js?v=602" not in doses
    historical = source("tests/test_release602_mobile_bundle.py")
    assert '"tracker-dose-fast602.js?v=710"' in historical
    worker = source("scripts/tracker-blend-vial710.sh")
    assert "scripts/tracker-impact-preflight604.py" in worker
    assert "RELEASE_710_ASSET_IMPACT_PREFLIGHT=PASSED" in worker
