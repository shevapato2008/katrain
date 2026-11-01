"""The new catalog keeps the legacy integer wallet denomination."""

from decimal import Decimal

import pytest

from katrain.web.core import billing_catalog as catalog


def test_catalog_prices_and_three_week_reference_budget():
    assert catalog.CATALOG_VERSION == "membership_20261102_v1"
    assert {key: (p["amount_fen"], p["term_units"], p["week_units"]) for key, p in catalog.PLANS.items()} == {
        "plus": (3900, 9030, 3010),
        "pro": (9900, 27090, 9030),
        "max": (19900, 72240, 24080),
    }
    assert all(plan["week_units"] * 3 == plan["term_units"] for plan in catalog.PLANS.values())
    assert catalog.PLANS["max"]["sellable"] is False
    assert catalog.MODEL_SHA256 == "93bdb63a3bfae4a70db0cb5265287495ecfc10b1ba1cc6814feeba1cdf055871"


def test_recharge_keeps_exact_old_credits_and_two_decimal_display():
    assert [(p["amount_fen"], p["credits"]) for p in catalog.TOPUPS.values()] == [
        (1000, 1000),
        (3000, 3000),
        (10000, 10000),
    ]
    assert catalog.wallet_display_points(42) == "0.42"
    assert catalog.wallet_display_points(3300) == "33.00"
    assert catalog.wallet_display_points(1) == "0.01"
    assert Decimal(catalog.wallet_display_points(123456789)) == Decimal("1234567.89")


@pytest.mark.parametrize("profile,visits,factor", [("normal", 500, 1), ("advanced", 2000, 4)])
def test_report_accounts_for_initial_and_all_move_positions(profile, visits, factor):
    assert catalog.PROFILES[profile]["visits"] == visits
    assert catalog.position_units(profile) == factor
    assert catalog.report_units(1, profile) == 2 * factor
    assert catalog.report_units(300, profile) == 301 * factor
    assert catalog.report_units(500, profile) == 501 * factor


@pytest.mark.parametrize("moves", [0, -1, 501, 1.2, True])
def test_report_requires_one_to_five_hundred_real_moves(moves):
    with pytest.raises(ValueError):
        catalog.report_units(moves, "normal")


def test_position_allows_zero_move_board_and_rejects_unknown_profile():
    assert catalog.position_units("normal", move_count=0) == 1
    with pytest.raises(ValueError):
        catalog.position_units("custom")
