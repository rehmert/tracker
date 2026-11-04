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
    assert "pk.js?v=pk-batch41-20261104" in html
    assert "tracker-pk-multi-schedule.js?v=batch41" in html
    assert "'pk-mode-multi'" in js
    assert '"/pk/what-if/multi-preview"' in multi
    assert "values_percent" in multi

    Environment().parse(html)


def test_prior_pk_cache_assertion_is_updated():
    legacy = (
        ROOT / "tests/test_pk_variable_schedule.py"
    ).read_text()
    assert '"pk.js?v=pk-batch41-20261104"' in legacy
