"""Versioned membership prices and integer request budgets.

A display point is 100 existing wallet credits. No stored balance is rescaled.
These rules apply only to the membership billing version; legacy prices remain
in analysis_cost.py and the original order snapshots.
"""

CATALOG_VERSION = "membership_20261102_v1"
MODEL_SHA256 = "93bdb63a3bfae4a70db0cb5265287495ecfc10b1ba1cc6814feeba1cdf055871"
CREDITS_PER_DISPLAY_POINT = 100
TERM_DAYS = 30
MAX_REPORT_MOVES = 500

PLANS = {
    "plus": {"amount_fen": 3900, "term_units": 9030, "week_units": 3010, "sellable": True},
    "pro": {"amount_fen": 9900, "term_units": 27090, "week_units": 9030, "sellable": True},
    "max": {"amount_fen": 19900, "term_units": 72240, "week_units": 24080, "sellable": False},
}
TOPUPS = {
    "topup_10": {"amount_fen": 1000, "credits": 1000},
    "topup_30": {"amount_fen": 3000, "credits": 3000},
    "topup_100": {"amount_fen": 10000, "credits": 10000},
}
PROFILES = {
    "normal": {"visits": 500, "units_per_position": 1, "model_sha256": MODEL_SHA256},
    "advanced": {"visits": 2000, "units_per_position": 4, "model_sha256": MODEL_SHA256},
}


def get_profile(profile: str) -> dict:
    try:
        return PROFILES[profile]
    except (KeyError, TypeError):
        raise ValueError("Unknown analysis profile") from None


def position_units(profile: str, *, move_count: int = 0) -> int:
    if type(move_count) is not int or not 0 <= move_count <= MAX_REPORT_MOVES:
        raise ValueError("Position requires 0..500 moves")
    return get_profile(profile)["units_per_position"]


def report_units(move_count: int, profile: str = "normal") -> int:
    if type(move_count) is not int or not 1 <= move_count <= MAX_REPORT_MOVES:
        raise ValueError("Report requires 1..500 moves")
    return (move_count + 1) * position_units(profile)


def wallet_display_points(credits: int) -> str:
    if type(credits) is not int:
        raise ValueError("Wallet credits must be an integer")
    sign = "-" if credits < 0 else ""
    whole, fraction = divmod(abs(credits), CREDITS_PER_DISPLAY_POINT)
    return f"{sign}{whole}.{fraction:02d}"
