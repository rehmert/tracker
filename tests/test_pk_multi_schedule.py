"""Read-only PK multi-schedule comparison regression coverage."""

from datetime import datetime
from pathlib import Path

import pytest
from jinja2 import Environment
from pydantic import ValidationError

from app.models import Compound
from app.routers.pk import (
    MultiWhatIfInput,
    WhatIfProtocol,
    preview_multi_what_if,
)

ROOT = Path(__file__).resolve().parents[1]


class FakeSession:
    def get(self, model, id_):
        names = {1: "Tirzepatide", 2: "Semaglutide"}
        if model is Compound and id_ in names:
            return Compound(
                id=id_,
                name=names[id_],
                category="peptide",
            )
        return None


def schedule(compound_id=1, **changes):
    values = dict(
        compound_id=compound_id,
        name=f"Schedule {compound_id}",
        start_at=datetime(2026, 11, 1, 9),
        interval_days=7,
        duration_days=28,
        offset_days=0,
        half_life_hours=120 if compound_id == 1 else 168,
        absorption_half_life_hours=12 if compound_id == 1 else 24,
        stages=[{"week": 1, "amount_mg": 5}],
    )
    values.update(changes)
    return WhatIfProtocol(**values)


def test_different_compounds_share_common_timeline():
    data = MultiWhatIfInput(schedules=[
        schedule(),
        schedule(
            2,
            start_at=datetime(2026, 11, 4, 9),
            offset_days=2,
        ),
    ])

    result = preview_multi_what_if(data, db=FakeSession())

    assert len(result["series"]) == 2
    assert len(result["at"]) > 2

    for series in result["series"]:
        assert len(series["values_percent"]) == len(result["at"])
        assert all(
            0 <= value <= 100
            for value in series["values_percent"]
        )
        assert max(series["values_percent"]) == pytest.approx(100)

    assert result["series"][0]["values_percent"] != (
        result["series"][1]["values_percent"]
    )
    assert "not measured" in result["disclaimer"]


def test_same_compound_schedules_are_independent():
    result = preview_multi_what_if(
        MultiWhatIfInput(schedules=[
            schedule(),
            schedule(interval_days=3.5),
        ]),
        db=FakeSession(),
    )

    assert result["series"][0]["dose_count"] == 4
    assert result["series"][1]["dose_count"] == 8
    assert len(result["series"]) == 2


def test_rejects_more_than_four_schedules():
    with pytest.raises(ValidationError):
        MultiWhatIfInput(schedules=[schedule()] * 5)


def test_rejects_excessive_timeline():
    with pytest.raises(ValidationError):
        MultiWhatIfInput(schedules=[
            schedule(start_at=datetime(2024, 1, 1)),
            schedule(start_at=datetime(2026, 11, 1)),
        ])


def test_unsupported_compound_rejected():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        preview_multi_what_if(
            MultiWhatIfInput(schedules=[
                schedule(compound_id=999)
            ]),
            db=FakeSession(),
        )

    assert error.value.status_code == 400


def test_endpoint_has_no_database_writes():
    router = (ROOT / "app/routers/pk.py").read_text()

    body = router.split(
        '@router.post("/what-if/multi-preview")', 1
    )[1].split(
        "def verify_what_if_compound", 1
    )[0]

    assert "pk.series(" in body
    assert "what_if_doses(schedule)" in body

    for forbidden in ("db.add(", "db.delete(", "db.commit("):
        assert forbidden not in body


def test_template_and_client_wiring():
    html = (ROOT / "app/templates/pk.html").read_text()
    js = (ROOT / "app/static/pk.js").read_text()
    multi = (
        ROOT / "app/static/js/tracker-pk-multi-schedule.js"
    ).read_text()

    assert 'data-pk-mode="multi"' in html
    assert 'id="pkMultiWorkspace"' in html
    assert 'id="pkMultiPlot"' in html
    assert "pk.js?v=pk-batch50-20261104" in html
    assert "tracker-pk-multi-schedule.js?v=batch50" in html
    assert "'pk-mode-multi'" in js
    assert '"/pk/what-if/multi-preview"' in multi
    assert "values_percent" in multi

    Environment().parse(html)


def test_prior_pk_cache_assertion_is_updated():
    legacy = (
        ROOT / "tests/test_pk_variable_schedule.py"
    ).read_text()
    assert '"pk.js?v=pk-batch50-20261104"' in legacy


def test_batch42_staged_editor_and_duplicate():
    js = (
        ROOT / "app/static/js/tracker-pk-multi-schedule.js"
    ).read_text()

    assert "function addSchedule(initial = null)" in js
    assert "function readSchedule(box)" in js
    assert "initial.stages.forEach(stage => addStage(stage))" in js
    assert "const copy = readSchedule(box);" in js
    assert 'copy.name = copy.name.slice(0, 112) + " (copy)"' in js
    assert "addSchedule(copy)" in js
    assert "interval_days: interval" in js
    assert "weeks[0] !== 1" in js


def test_batch42_csv_export_and_current_cache():
    html = (ROOT / "app/templates/pk.html").read_text()
    js = (
        ROOT / "app/static/js/tracker-pk-multi-schedule.js"
    ).read_text()

    assert 'id="pkMultiExportCsv" disabled' in html
    assert "function exportCsv()" in js
    assert "values_percent[index]" in js
    assert 'container.addEventListener("input", invalidate)' in js
    assert 'container.addEventListener("change", invalidate)' in js
    assert "lastResult = result" in js
    assert "tracker-pk-multi-schedule.js?v=batch50" in html


def test_batch43_custom_schedule_names():
    js = (
        ROOT / "app/static/js/tracker-pk-multi-schedule.js"
    ).read_text()

    assert 'inputField("Schedule name", "name"' in js
    assert "name: initial.name" in js
    assert "name," in js
    assert "const schedules = entries.map(box => readSchedule(box));" in js
    assert "validateCommonTimeline(schedules);" in js


def test_batch43_summary_and_result_invalidation():
    js = (
        ROOT / "app/static/js/tracker-pk-multi-schedule.js"
    ).read_text()
    html = (ROOT / "app/templates/pk.html").read_text()

    assert 'id="pkMultiMetrics"' in html
    assert "function renderMetrics(data)" in js
    assert "series.compound_name" in js
    assert "series.dose_count" in js
    assert "renderMetrics(result)" in js
    assert "revision !== requestedRevision" in js
    assert "lastResult = null" in js
    assert "ctx.clearRect(" in js
    assert "tracker-pk-multi-schedule.js?v=batch50" in html

    Environment().parse(html)


def test_batch43_multi_preview_is_read_only():
    router = (ROOT / "app/routers/pk.py").read_text()
    section = router.split(
        '@router.post("/what-if/multi-preview")', 1
    )[1].split("def verify_what_if_compound", 1)[0]

    for forbidden in (
        "db.add(", "db.commit(", "db.delete("
    ):
        assert forbidden not in section


def test_batch44_time_weighted_summary():
    js = (
        ROOT / "app/static/js/tracker-pk-multi-schedule.js"
    ).read_text()
    html = (ROOT / "app/templates/pk.html").read_text()

    assert "function exposureStats(times, values)" in js
    assert "Date.parse(times[i - 1] + \"Z\")" in js
    assert "area / totalHours" in js
    assert "stats.trough.toFixed(1)" in js
    assert "stats.range.toFixed(1)" in js
    assert "stats.mean.toFixed(1)" in js
    assert "Time-weighted mean (%)" in js
    assert "tracker-pk-multi-schedule.js?v=batch50" in html


def test_batch44_png_export_and_invalidation():
    js = (
        ROOT / "app/static/js/tracker-pk-multi-schedule.js"
    ).read_text()
    html = (ROOT / "app/templates/pk.html").read_text()

    assert 'id="pkMultiExportPng" disabled' in html
    assert "function exportChartPng()" in js
    assert "canvas.toBlob(" in js
    assert '"image/png"' in js
    assert "revision !== exportRevision" in js
    assert "exportPng.disabled = true" in js
    assert "exportPng.disabled = false" in js
    assert "tracker-pk-multi-comparison.png" in js

    Environment().parse(html)


def test_batch45_preset_source_contracts():
    js = (
        ROOT / "app/static/js/tracker-pk-multi-schedule.js"
    ).read_text()
    html = (ROOT / "app/templates/pk.html").read_text()

    for marker in (
        'id="pkMultiExportPreset"',
        'id="pkMultiImportPreset"',
        'id="pkMultiPresetFile"',
        "tracker-pk-multi-schedule.js?v=batch50",
        "tracker-pk-multi-schedule.css?v=batch49",
    ):
        assert marker in html

    for marker in (
        "function validatePreset(raw)",
        "function downloadPreset()",
        "async function loadPreset(file)",
        "JSON.parse(await file.text())",
        "JSON.stringify(preset, null, 2)",
        "window.confirm(",
        "container.replaceChildren()",
        "schedules.forEach(schedule => addSchedule(schedule))",
        "MAX_PRESET_BYTES",
        "PRESET_VERSION",
        "schedule.offset_days >= schedule.duration_days",
    ):
        assert marker in js

    Environment().parse(html)


def test_batch45_presets_do_not_add_backend_write_routes():
    router = (ROOT / "app/routers/pk.py").read_text()
    section = router.split(
        '@router.post("/what-if/multi-preview")', 1
    )[1].split("def verify_what_if_compound", 1)[0]

    assert "what_if_doses(schedule)" in section

    for forbidden in ("db.add(", "db.commit(", "db.delete("):
        assert forbidden not in section


def test_batch46_portable_compound_resolution():
    js = (
        ROOT / "app/static/js/tracker-pk-multi-schedule.js"
    ).read_text()

    assert 'schedule.compound_name !== undefined' in js
    assert 'const matches = choices.filter(option =>' in js
    assert 'matches.length !== 1' in js
    assert 'compound = matches[0]' in js
    assert 'compound_id: Number(compound.value)' in js
    assert 'compound_name:' in js
    assert 'validatePreset({' in js


def test_batch46_legacy_preset_compatibility():
    js = (
        ROOT / "app/static/js/tracker-pk-multi-schedule.js"
    ).read_text()

    assert 'const PRESET_VERSION = 1;' in js
    assert 'Legacy Batch 45 presets only have local IDs.' in js
    assert 'Number(option.value) === schedule.compound_id' in js


def test_batch46_asset_and_read_only_contracts():
    html = (ROOT / "app/templates/pk.html").read_text()
    router = (ROOT / "app/routers/pk.py").read_text()

    assert "tracker-pk-multi-schedule.js?v=batch50" in html
    assert "tracker-pk-multi-schedule.css?v=batch49" in html

    section = router.split(
        '@router.post("/what-if/multi-preview")', 1
    )[1].split("def verify_what_if_compound", 1)[0]

    for forbidden in ("db.add(", "db.commit(", "db.delete("):
        assert forbidden not in section

    Environment().parse(html)


def test_batch47_timeline_alignment_controls():
    html = (ROOT / "app/templates/pk.html").read_text()
    js = (
        ROOT / "app/static/js/tracker-pk-multi-schedule.js"
    ).read_text()

    assert 'id="pkMultiAlignStarts"' in html
    assert 'id="pkMultiMatchDurations"' in html
    assert "function alignScheduleStarts()" in js
    assert "function matchScheduleDurations()" in js
    assert 'entry.querySelector(".pk-multi-start").value = start' in js
    assert "const incompatible = entries.slice(1).some" in js
    assert "offset >= duration" in js
    assert "invalidate();" in js

    Environment().parse(html)


def test_batch47_preflight_and_asset_versions():
    html = (ROOT / "app/templates/pk.html").read_text()
    js = (
        ROOT / "app/static/js/tracker-pk-multi-schedule.js"
    ).read_text()

    assert "function validateCommonTimeline(schedules)" in js
    assert "validateCommonTimeline(schedules);" in js
    assert "730 * 86400000" in js
    assert "Combined comparison timeline exceeds 730 days." in js
    assert "tracker-pk-multi-schedule.js?v=batch50" in html
    assert "tracker-pk-multi-schedule.css?v=batch49" in html


def test_batch47_multi_preview_remains_read_only():
    router = (ROOT / "app/routers/pk.py").read_text()
    section = router.split(
        '@router.post("/what-if/multi-preview")', 1
    )[1].split("def verify_what_if_compound", 1)[0]

    for forbidden in ("db.add(", "db.commit(", "db.delete("):
        assert forbidden not in section


def test_batch48_schedule_ordering():
    js = (
        ROOT / "app/static/js/tracker-pk-multi-schedule.js"
    ).read_text()

    assert "function refreshScheduleOrder()" in js
    assert 'up.textContent = "Move up"' in js
    assert 'down.textContent = "Move down"' in js
    assert "container.insertBefore(" in js
    assert "box, box.previousElementSibling" in js
    assert "box.nextElementSibling, box" in js
    assert "refreshScheduleOrder();" in js
    assert "if (up) up.disabled = index === 0" in js
    assert "add.disabled = entries.length >= 4" in js


def test_batch48_duplicate_name_and_asset_versions():
    html = (ROOT / "app/templates/pk.html").read_text()
    js = (
        ROOT / "app/static/js/tracker-pk-multi-schedule.js"
    ).read_text()

    assert 'copy.name = copy.name.slice(0, 112) + " (copy)"' in js
    assert "addSchedule(copy)" in js
    assert "tracker-pk-multi-schedule.js?v=batch50" in html
    assert "tracker-pk-multi-schedule.css?v=batch49" in html

    Environment().parse(html)


def test_batch48_payload_still_uses_display_order():
    js = (
        ROOT / "app/static/js/tracker-pk-multi-schedule.js"
    ).read_text()

    assert "const entries = [...container.children]" in js
    assert (
        "const schedules = entries.map(box => readSchedule(box));"
        in js
    )
    assert "validateCommonTimeline(schedules);" in js


def test_batch48_remains_read_only():
    router = (ROOT / "app/routers/pk.py").read_text()

    section = router.split(
        '@router.post("/what-if/multi-preview")', 1
    )[1].split("def verify_what_if_compound", 1)[0]

    for forbidden in ("db.add(", "db.commit(", "db.delete("):
        assert forbidden not in section


def test_batch49_compact_schedule_controls():
    js = (
        ROOT / "app/static/js/tracker-pk-multi-schedule.js"
    ).read_text()
    html = (ROOT / "app/templates/pk.html").read_text()

    for marker in (
        "function refreshScheduleSummary(box)",
        "function setScheduleCollapsed(box, collapsed)",
        "classList.toggle(\"pk-multi-collapsed\", collapsed)",
        'toggle.textContent = collapsed ?',
        '"aria-expanded", String(!collapsed)',
        "setScheduleCollapsed(box, true)",
        "setScheduleCollapsed(box, false)",
        "refreshScheduleSummary(box);",
    ):
        assert marker in js

    for marker in (
        'id="pkMultiCollapseAll"',
        'id="pkMultiExpandAll"',
        "tracker-pk-multi-schedule.js?v=batch50",
        "tracker-pk-multi-schedule.css?v=batch49",
    ):
        assert marker in html

    Environment().parse(html)


def test_batch49_preserves_existing_simulation_contract():
    js = (
        ROOT / "app/static/js/tracker-pk-multi-schedule.js"
    ).read_text()

    for marker in (
        "function payload()",
        "const schedules = entries.map(box => readSchedule(box));",
        "validateCommonTimeline(schedules);",
        "function validatePreset(raw)",
        "function renderMetrics(data)",
        "addSchedule(copy)",
        "function refreshScheduleOrder()",
    ):
        assert marker in js


def test_batch49_remains_read_only():
    router = (ROOT / "app/routers/pk.py").read_text()

    section = router.split(
        '@router.post("/what-if/multi-preview")', 1
    )[1].split("def verify_what_if_compound", 1)[0]

    for forbidden in ("db.add(", "db.commit(", "db.delete("):
        assert forbidden not in section


def test_batch50_shared_chart_axes_and_cache():
    html = (ROOT / "app/templates/pk.html").read_text()
    main = (ROOT / "app/static/pk.js").read_text()
    multi = (
        ROOT / "app/static/js/tracker-pk-multi-schedule.js"
    ).read_text()
    axes = (
        ROOT / "app/static/js/tracker-pk-axes.js"
    ).read_text()

    assert "tracker-pk-axes.js?v=batch50" in html
    assert "pk.js?v=pk-batch50-20261104" in html
    assert "tracker-pk-multi-schedule.js?v=batch50" in html

    assert html.index("tracker-pk-axes.js?v=batch50") < (
        html.index("pk.js?v=pk-batch50-20261104")
    )

    assert main.count("window.trackerPkAxes.draw({") == 3
    assert multi.count("window.trackerPkAxes.draw({") == 1

    for marker in (
        "Elapsed time (",
        "Normalized exposure (%)",
        "Modeled exposure (mg-eq)",
        "hours",
        "days",
        "weeks",
        "const fraction = step / 4",
        "ctx.fillText(",
        "ctx.restore();",
    ):
        assert marker in axes

    Environment().parse(html)


def test_batch50_preserves_pk_simulation_data_contracts():
    main = (ROOT / "app/static/pk.js").read_text()
    multi = (
        ROOT / "app/static/js/tracker-pk-multi-schedule.js"
    ).read_text()

    assert "function draw(data)" in main
    assert "function plot(data)" in multi
    assert "function payload()" in multi
    assert "validateCommonTimeline(schedules);" in multi
    assert "function validatePreset(raw)" in multi
    assert "function renderMetrics(data)" in multi
