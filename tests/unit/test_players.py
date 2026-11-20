import pytest

from app.comparison import compare_players
from app.players import find_player, load_dataset

FIRST = {"name": "First", "pts": 20, "reb": 8, "to": 2}
SECOND = {"name": "Second", "pts": 18, "reb": 6, "to": 3}


def test_finds_player_by_id():
    player = find_player(load_dataset(), "luka_doncic")
    assert player["name"] == "Luka Doncic"


def test_finds_name_with_spaces_and_different_case():
    player = find_player(load_dataset(), "  DONOVAN MITCHELL  ")
    assert player["id"] == "donovan_mitchell"


def test_unknown_player_is_reported():
    with pytest.raises(ValueError, match="Player not found"):
        find_player(load_dataset(), "unknown_player")


@pytest.mark.parametrize("first,second", [(FIRST, SECOND), (SECOND, FIRST)])
def test_dominant_player_is_recommended_in_either_order(first, second):
    assert "Recommendation: First." in compare_players(first, second)


def test_lower_turnovers_break_otherwise_equal_comparison():
    second = {**FIRST, "name": "Second", "to": 3}
    assert "Recommendation: First." in compare_players(FIRST, second)


def test_equal_statistics_produce_tie():
    second = {**FIRST, "name": "Second"}
    assert "The players are tied in PTS, REB, and TO." in compare_players(FIRST, second)


def test_split_advantages_request_priority():
    first = {"name": "First", "pts": 22, "reb": 6, "to": 3}
    second = {"name": "Second", "pts": 18, "reb": 9, "to": 2}
    assert "Which category matters most" in compare_players(first, second)


def test_missing_stat_prevents_full_recommendation():
    second = {**SECOND, "to": None}
    reply = compare_players(FIRST, second)
    assert "Missing statistics for Second: TO" in reply
    assert "Recommendation:" not in reply
