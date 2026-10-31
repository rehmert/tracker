

"""Regression tests for Tracker bulk vial editing."""

from datetime import date
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.quick
from starlette.datastructures import FormData

from app.routers.vials import (
    _bulk_parse,
    _bulk_validate,
    _bulk_snapshot,
    _bulk_rows,
)


def form(*items):
    return FormData(items)


def vial(
    vid=1,
    status="sealed",
    lot="LOT-A",
    received_on=None,
    first_punctured_on=None,
    first_dosed_on=None,
    doses=None,
):
    from app.routers.vials import BULK_FIELDS

    values = {
        key: None
        for key in BULK_FIELDS
    }

    values.update({
        "status": status,
        "lot": lot,
        "cap_color": "",
        "storage_notes": "",
        "notes": "",
        "use_coa_content": False,
        "received_on": received_on,
        "first_punctured_on": first_punctured_on,
        "first_dosed_on": first_dosed_on,
    })

    return SimpleNamespace(
        id=vid,
        compound_id=10,
        compound=SimpleNamespace(name="Test compound"),
        label=f"Test vial {vid}",
        doses=doses if doses is not None else [],
        **values,
    )


def test_parse_multiple_vials():
    ids, changes = _bulk_parse(form(
        ("vial_ids", "2"),
        ("vial_ids", "1"),
        ("vial_ids", "2"),
        ("mode_lot", "set"),
        ("value_lot", "LOT-B"),
    ))

    assert ids == [1, 2]
    assert changes == {"lot": "LOT-B"}


def test_parse_keep_preserves_fields():
    ids, changes = _bulk_parse(form(
        ("vial_ids", "1"),
        ("mode_lot", "keep"),
        ("value_lot", "SHOULD-NOT-APPLY"),
        ("mode_cap_color", "set"),
        ("value_cap_color", "Blue"),
    ))

    assert ids == [1]
    assert changes == {"cap_color": "Blue"}


def test_parse_clear_text():
    _, changes = _bulk_parse(form(
        ("vial_ids", "1"),
        ("mode_lot", "clear"),
    ))

    assert changes == {"lot": ""}


def test_parse_clear_date():
    _, changes = _bulk_parse(form(
        ("vial_ids", "1"),
        ("mode_expires_on", "clear"),
    ))

    assert changes == {"expires_on": None}


def test_parse_rejects_clear_status():
    with pytest.raises(ValueError):
        _bulk_parse(form(
            ("vial_ids", "1"),
            ("mode_status", "clear"),
        ))


def test_parse_rejects_empty_selection():
    with pytest.raises(ValueError):
        _bulk_parse(form(
            ("mode_lot", "set"),
            ("value_lot", "LOT-B"),
        ))


def test_parse_rejects_empty_changes():
    with pytest.raises(ValueError):
        _bulk_parse(form(
            ("vial_ids", "1"),
        ))


def test_parse_rejects_excessive_selection():
    items = [
        ("vial_ids", str(i))
        for i in range(1, 1002)
    ]

    items += [
        ("mode_lot", "set"),
        ("value_lot", "LOT-B"),
    ]

    with pytest.raises(ValueError):
        _bulk_parse(form(*items))


def test_parse_rejects_invalid_id():
    with pytest.raises(ValueError):
        _bulk_parse(form(
            ("vial_ids", "invalid"),
            ("mode_lot", "set"),
            ("value_lot", "LOT-B"),
        ))


def test_parse_rejects_invalid_status():
    with pytest.raises(ValueError):
        _bulk_parse(form(
            ("vial_ids", "1"),
            ("mode_status", "set"),
            ("value_status", "not-a-status"),
        ))


def test_validate_valid_date_sequence():
    v = vial(
        received_on=date(2026, 1, 1),
        first_punctured_on=date(2026, 1, 2),
        first_dosed_on=date(2026, 1, 3),
    )

    _bulk_validate([v], {"lot": "LOT-B"})


def test_validate_rejects_puncture_before_receipt():
    v = vial(
        received_on=date(2026, 1, 10),
        first_punctured_on=date(2026, 1, 12),
    )

    with pytest.raises(ValueError):
        _bulk_validate(
            [v],
            {"first_punctured_on": date(2026, 1, 5)},
        )


def test_validate_rejects_dose_before_puncture():
    v = vial(
        first_punctured_on=date(2026, 1, 10),
        first_dosed_on=date(2026, 1, 12),
    )

    with pytest.raises(ValueError):
        _bulk_validate(
            [v],
            {"first_dosed_on": date(2026, 1, 5)},
        )


def test_validate_rejects_sealed_with_doses():
    v = vial(
        status="in_use",
        doses=[SimpleNamespace(id=100)],
    )

    with pytest.raises(ValueError):
        _bulk_validate(
            [v],
            {"status": "sealed"},
        )


def test_snapshot_stable_for_same_data():
    v = vial()

    first = _bulk_snapshot(
        [v],
        {"lot": "LOT-B"},
    )

    second = _bulk_snapshot(
        [v],
        {"lot": "LOT-B"},
    )

    assert first == second


def test_snapshot_changes_when_vial_changes():
    v = vial()

    before = _bulk_snapshot(
        [v],
        {"lot": "LOT-B"},
    )

    v.cap_color = "Blue"

    after = _bulk_snapshot(
        [v],
        {"lot": "LOT-B"},
    )

    assert before != after


def test_snapshot_changes_when_dose_added():
    v = vial()

    before = _bulk_snapshot(
        [v],
        {"lot": "LOT-B"},
    )

    v.doses.append(SimpleNamespace(id=100))

    after = _bulk_snapshot(
        [v],
        {"lot": "LOT-B"},
    )

    assert before != after


def test_snapshot_changes_when_request_changes():
    v = vial()

    before = _bulk_snapshot(
        [v],
        {"lot": "LOT-B"},
    )

    after = _bulk_snapshot(
        [v],
        {"lot": "LOT-C"},
    )

    assert before != after


def test_preview_rows_identify_unchanged_values():
    v = vial(lot="LOT-A")

    rows = _bulk_rows(
        [v],
        {"lot": "LOT-A"},
    )

    assert len(rows) == 1
    assert rows[0]["changed"] is False


def test_preview_rows_identify_changed_values():
    v = vial(lot="LOT-A")

    rows = _bulk_rows(
        [v],
        {"lot": "LOT-B"},
    )

    assert len(rows) == 1
    assert rows[0]["changed"] is True
    assert rows[0]["current"] == "LOT-A"
    assert rows[0]["proposed"] == "LOT-B"
