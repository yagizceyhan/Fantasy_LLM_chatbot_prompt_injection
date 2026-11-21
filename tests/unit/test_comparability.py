import pytest

from app.comparison import compare_players


@pytest.mark.parametrize(
    "field,left,right",
    [
        ("period", "S1", "L5"),
        ("season", "S1", "S2"),
        ("season_type", "regular", "playoffs"),
        ("stat_basis", "per_game", "totals"),
    ],
)
def test_incompatible_metadata_prevents_recommendation(field, left, right):
    first = {"name": "A", "pts": 20, "reb": 8, "to": 2, field: left}
    second = {"name": "B", "pts": 18, "reb": 6, "to": 3, field: right}

    reply = compare_players(first, second)

    assert "Incompatible" in reply
    assert left in reply and right in reply
    assert "Recommendation:" not in reply


def test_missing_stat_takes_precedence_over_period_mismatch():
    first = {"name": "A", "pts": 20, "reb": 8, "to": 2, "period": "S1"}
    second = {"name": "B", "pts": 18, "reb": 6, "to": None, "period": "L5"}

    reply = compare_players(first, second)

    assert "Missing statistics for B: TO" in reply
    assert "Recommendation:" not in reply
