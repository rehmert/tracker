"""Behavioral tests for date-aware vial recommendations."""

from datetime import date, timedelta
from types import SimpleNamespace

from app.vial_recommendation import (
    rank_vials,
    date_warnings,
    first_use_date,
)


TODAY = date(2026, 11, 1)


def vial(
    id,
    status="in_use",
    first_punctured_on=None,
    first_dosed_on=None,
    expires_on=None,
    beyond_use_on=None,
):
    return SimpleNamespace(
        id=id,
        status=status,
        first_punctured_on=first_punctured_on,
        first_dosed_on=first_dosed_on,
        expires_on=expires_on,
        beyond_use_on=beyond_use_on,
    )


def eligible(*ids):
    return {
        id: {"eligible": True}
        for id in ids
    }


def test_prefers_in_use_over_sealed():
    selected, _ = rank_vials(
        [
            vial(1, status="sealed"),
            vial(2, status="in_use"),
        ],
        eligible(1, 2),
        TODAY,
    )

    assert selected == 2


def test_prefers_earliest_first_use():
    selected, _ = rank_vials(
        [
            vial(
                1,
                first_punctured_on=TODAY - timedelta(days=2),
            ),
            vial(
                2,
                first_punctured_on=TODAY - timedelta(days=10),
            ),
        ],
        eligible(1, 2),
        TODAY,
    )

    assert selected == 2


def test_known_date_preferred_over_unknown():
    selected, _ = rank_vials(
        [
            vial(1),
            vial(
                2,
                first_dosed_on=TODAY - timedelta(days=3),
            ),
        ],
        eligible(1, 2),
        TODAY,
    )

    assert selected == 2


def test_insufficient_vial_excluded():
    selected, _ = rank_vials(
        [vial(1), vial(2)],
        {
            1: {"eligible": False},
            2: {"eligible": True},
        },
        TODAY,
    )

    assert selected == 2


def test_expired_vial_excluded():
    selected, warnings = rank_vials(
        [
            vial(
                1,
                expires_on=TODAY - timedelta(days=1),
            ),
            vial(2),
        ],
        eligible(1, 2),
        TODAY,
    )

    assert selected == 2
    assert "Expiration date reached" in warnings[1]


def test_beyond_use_vial_excluded():
    selected, warnings = rank_vials(
        [
            vial(1, beyond_use_on=TODAY),
            vial(2),
        ],
        eligible(1, 2),
        TODAY,
    )

    assert selected == 2
    assert "Beyond-use date reached" in warnings[1]


def test_no_eligible_vials():
    selected, _ = rank_vials(
        [vial(1)],
        {1: {"eligible": False}},
        TODAY,
    )

    assert selected is None


def test_id_is_final_tiebreaker():
    selected, _ = rank_vials(
        [vial(9), vial(3)],
        eligible(9, 3),
        TODAY,
    )

    assert selected == 3


def test_missing_dates_do_not_trigger_expiration():
    assert date_warnings(vial(1), TODAY) == []


def test_earliest_known_use_date():
    item = vial(
        1,
        first_punctured_on=TODAY - timedelta(days=2),
        first_dosed_on=TODAY - timedelta(days=5),
    )

    assert first_use_date(item) == (
        TODAY - timedelta(days=5)
    )
