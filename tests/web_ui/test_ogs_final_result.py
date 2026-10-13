import pytest

from katrain.web.platforms.ogs.results import parse_finished_result


def finished(outcome, winner=7):
    return {
        "phase": "finished",
        "players": {"black": {"id": 7}, "white": {"id": 8}},
        "winner": winner,
        "outcome": outcome,
    }


@pytest.mark.parametrize(
    ("outcome", "winner", "expected"),
    [
        ("Resignation", 7, "B+R"),
        ("Resignation", 8, "W+R"),
        ("Timeout", 8, "W+T"),
        ("59.5 points", 8, "W+59.5"),
        ("1 point", 7, "B+1"),
        ("Cancellation", 7, "Void"),
        ("Resignation", 999, "Void"),
    ],
)
def test_finished_result_uses_remote_winner_and_outcome(outcome, winner, expected):
    assert parse_finished_result(finished(outcome, winner)) == expected


def test_unfinished_game_has_no_authoritative_result():
    data = finished("Resignation")
    data["phase"] = "stone removal"
    with pytest.raises(ValueError, match="finished"):
        parse_finished_result(data)


def test_finished_result_waits_for_missing_winner_or_outcome():
    with pytest.raises(ValueError, match="winner"):
        parse_finished_result(finished("Resignation", None))
    data = finished("Resignation")
    data.pop("outcome")
    with pytest.raises(ValueError, match="outcome"):
        parse_finished_result(data)
