"""Two guests at the two dart boards at once play a match: a winner drawn from form, with less luck than dice."""

import pytest

from dice_hall import MIDDLING, advance, guest, happened, start, table_hall, who
from tavern.hall.rules import default_rules
from tavern.social.darts import win_chance as darts_chance
from tavern.social.dice import win_chance as dice_chance

RULES = default_rules()["dice"]
SHARP = {"patience": 1.0, "curiosity": 1.0, "courage": 1.0}
DULL = {"patience": 0.0, "curiosity": 0.0, "courage": 0.0}


def player(actor_id: str, row: int, traits: dict[str, float] | None = None) -> dict:
    """A guest standing in front of the board on a row of the west wall."""
    return guest(actor_id, (2, row), traits)


def throw(world: dict, actor_id: str, board: str) -> None:
    assert start(world, actor_id, "play_darts", board)["accepted"]


def test_the_hall_has_two_boards_side_by_side_on_the_west_wall() -> None:
    world = table_hall()
    boards = sorted((item["x"], item["y"]) for item in world["map"]["objects"] if item["kind"] == "darts")
    assert boards == [(1, 8), (1, 9)]


def test_two_players_at_the_two_boards_get_a_winner_and_a_loser() -> None:
    world = table_hall(player("ada", 8), player("bea", 9))
    throw(world, "ada", "darts")
    throw(world, "bea", "darts-2")
    advance(world, 14)
    assert (len(happened(world, "darts_won")), len(happened(world, "darts_lost"))) == (1, 1)


def test_a_player_alone_plays_no_match() -> None:
    world = table_hall(player("ada", 8))
    throw(world, "ada", "darts")
    advance(world, 14)
    assert (happened(world, "darts_won"), happened(world, "darts_lost")) == ([], [])


def test_a_neighbour_who_has_only_just_begun_is_no_opponent() -> None:
    world = table_hall(player("ada", 8), player("bea", 9))
    throw(world, "ada", "darts")
    advance(world, 9)
    throw(world, "bea", "darts-2")
    advance(world, 14)
    assert happened(world, "darts_won") == []


def test_one_throw_is_one_match_even_when_the_board_next_door_changes_hands() -> None:
    world = table_hall(player("ada", 8), player("bea", 9), guest("cid", (3, 7)))
    throw(world, "ada", "darts")
    advance(world, 4)
    throw(world, "bea", "darts-2")
    advance(world, 6.5)
    assert who(world, "ada")["action"] is None
    throw(world, "cid", "darts")
    advance(world, 8)
    assert len(happened(world, "darts_won")) == 1


def test_the_winner_and_the_loser_each_keep_a_thought_of_the_game() -> None:
    world = table_hall(player("ada", 8, SHARP), player("bea", 9, DULL))
    throw(world, "ada", "darts")
    throw(world, "bea", "darts-2")
    advance(world, 14)
    kept = [item["kind"] for actor_id in ("ada", "bea") for item in who(world, actor_id)["thoughts"]]
    assert sorted(kept) == ["lost_at_darts", "won_at_darts"]


@pytest.mark.parametrize("first, second, expected", [
    pytest.param(MIDDLING, MIDDLING, 0.5, id="equals-are-even"),
    pytest.param(SHARP, DULL, 0.9, id="the-sharper-is-capped-at-nine-in-ten"),
    pytest.param(DULL, SHARP, 0.1, id="the-duller-keeps-one-in-ten"),
])
def test_darts_chance(first: dict[str, float], second: dict[str, float], expected: float) -> None:
    a = {"traits": first, "drunkenness": 0.0}
    b = {"traits": second, "drunkenness": 0.0}
    assert darts_chance(a, b, RULES) == pytest.approx(expected)


def test_darts_leave_less_to_luck_than_dice() -> None:
    steady = {"traits": {"patience": 0.6, "curiosity": 0.5, "courage": 0.5}, "drunkenness": 0.0}
    shaky = {"traits": MIDDLING, "drunkenness": 0.0}
    assert darts_chance(steady, shaky, RULES) > dice_chance(steady, shaky, RULES) > 0.5
