"""A game of dice: two guests seated at the dice table, a winner drawn from traits and drink."""

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.persistence import parse_world
from tavern.body.hearing import EVENT_SOUNDS
from tavern.evening.decisions import free_to_decide
from tavern.hall.rules import check_rules, default_rules
from tavern.hall.world import create_world, start_action, step_world
from tavern.social.dice import win_chance, winner

LAYOUT = json.loads((Path(__file__).parents[1] / "data" / "tavern.json").read_text())
RULES = default_rules()["dice"]
SHARP = {"patience": 1.0, "curiosity": 1.0, "courage": 1.0}
DULL = {"patience": 0.0, "curiosity": 0.0, "courage": 0.0}
MIDDLING = {"patience": 0.5, "curiosity": 0.5, "courage": 0.5}


def guest(actor_id: str, cell: tuple[int, int], traits: dict[str, float] | None = None, **fields: Any) -> dict[str, Any]:
    """Describe a visitor standing on a cell, bored enough to want a game."""
    return {"id": actor_id, "name": actor_id.capitalize(), "x": cell[0], "y": cell[1], "traits": traits or MIDDLING,
            "needs": {"boredom": 80, "social": 60}, **fields}


def table_hall(*actors: dict[str, Any]) -> dict[str, Any]:
    """The real hall with the visitors placed by hand and no arrival draws."""
    room = {key: value for key, value in LAYOUT.items() if key != "arrival"}
    return create_world({**room, "actors": list(actors)}, seed=3)


def two_players(**seed_and_traits: Any) -> dict[str, Any]:
    """Ada by the west chair and Bea by the east one, both sent to play."""
    world = table_hall(guest("ada", (8, 8), seed_and_traits.get("ada")), guest("bea", (12, 8), seed_and_traits.get("bea")))
    sit_down(world, "ada", "dice-chair-1")
    sit_down(world, "bea", "dice-chair-2")
    return world


def sit_down(world: dict[str, Any], actor_id: str, chair: str) -> None:
    """Send a visitor to play at a dice chair."""
    assert start_action(world, actor_id, {"id": f"play_dice:{chair}", "verb": "play_dice", "target_id": chair})["accepted"]


def advance(world: dict[str, Any], seconds: float) -> None:
    """Advance the world without requesting decisions."""
    for _ in range(round(seconds * 10)):
        step_world(world, 0.1)


def who(world: dict[str, Any], actor_id: str) -> dict[str, Any]:
    """Find a visitor in the hall."""
    return next(item for item in world["actors"] if item["id"] == actor_id)


def table(world: dict[str, Any]) -> dict[str, Any]:
    """The dice table."""
    return next(item for item in world["map"]["objects"] if item["id"] == "dice-table")


def happened(world: dict[str, Any], kind: str) -> list[str]:
    """The messages of logged events of a kind."""
    return [event["message"] for event in world["events"] if event["type"] == kind]


def fake_world(seed: int, tick: int = 1) -> dict[str, Any]:
    """A stand-in world for drawing a winner: the draw reads only the seed, tick and rules."""
    return {"seed": seed, "tick": tick, "rules": default_rules()}


def player(actor_id: str, traits: dict[str, float], drunkenness: float = 0.0) -> dict[str, Any]:
    """A stand-in visitor for the odds: the odds read only traits and drunkenness."""
    return {"id": actor_id, "traits": traits, "drunkenness": drunkenness}


@pytest.mark.parametrize("first, second, expected", [
    pytest.param(player("a", MIDDLING), player("b", MIDDLING), 0.5, id="equal-guests"),
    pytest.param(player("a", MIDDLING), player("b", MIDDLING, 0.45), 0.635, id="the-opponent-is-drunk"),
    pytest.param(player("a", MIDDLING, 0.45), player("b", MIDDLING), 0.365, id="the-first-is-drunk"),
    pytest.param(player("a", SHARP), player("b", DULL), 0.8, id="sharp-against-dull-is-capped"),
    pytest.param(player("a", DULL), player("b", SHARP), 0.2, id="dull-against-sharp-is-capped"),
    pytest.param(player("a", {}), player("b", {}), 0.5, id="missing-traits-count-as-middling"),
    pytest.param(player("a", {"patience": 1.0}), player("b", {}), 0.5 + 0.5 * 0.2, id="one-trait-more-patience"),
    pytest.param(player("a", {"courage": 0.9}), player("b", {"courage": 0.1}), 0.5 + 0.5 * 0.3 * 0.8, id="courage-weighs-three-tenths"),
    pytest.param(player("a", MIDDLING, 1.0), player("b", DULL), 0.45, id="dead-drunk-against-dull"),
])
def test_win_chance_follows_traits_and_drink(first: dict[str, Any], second: dict[str, Any], expected: float) -> None:
    assert win_chance(first, second, RULES) == pytest.approx(expected)


@pytest.mark.parametrize("first, second", [
    pytest.param(player("a", SHARP), player("b", DULL), id="sharp-and-dull"),
    pytest.param(player("a", MIDDLING, 0.3), player("b", {"patience": 0.9}, 0.1), id="mixed"),
    pytest.param(player("a", MIDDLING), player("b", MIDDLING), id="equal"),
])
def test_the_chances_of_the_two_seats_add_up_to_one(first: dict[str, Any], second: dict[str, Any]) -> None:
    assert win_chance(first, second, RULES) + win_chance(second, first, RULES) == pytest.approx(1.0)


@pytest.mark.parametrize("first, second, label", [
    pytest.param(player("a", MIDDLING, 1.5), player("b", MIDDLING), "Drunkenness", id="drunkenness-above-one"),
    pytest.param(player("a", MIDDLING, -0.1), player("b", MIDDLING), "Drunkenness", id="drunkenness-below-zero"),
    pytest.param(player("a", MIDDLING), player("b", {"courage": 2.0}), "courage", id="trait-above-one"),
    pytest.param(player("a", {"patience": -1.0}), player("b", MIDDLING), "patience", id="trait-below-zero"),
])
def test_win_chance_rejects_values_out_of_range(first: dict[str, Any], second: dict[str, Any], label: str) -> None:
    with pytest.raises(ValueError, match=label):
        win_chance(first, second, RULES)


@pytest.mark.parametrize("first, second, low, high", [
    pytest.param(player("a", SHARP), player("b", DULL), 0.72, 0.88, id="the-cap-wins-four-in-five"),
    pytest.param(player("a", MIDDLING), player("b", MIDDLING), 0.43, 0.57, id="equal-guests-split-evenly"),
    pytest.param(player("a", DULL), player("b", SHARP), 0.12, 0.28, id="the-dullard-still-wins-sometimes"),
])
def test_over_400_seeded_games_the_first_seat_wins_at_its_odds(first: dict[str, Any], second: dict[str, Any],
                                                                low: float, high: float) -> None:
    firsts = sum(winner(fake_world(seed), "dice-table", first, second) is first for seed in range(400))
    assert low <= firsts / 400 <= high


def test_the_same_seed_and_tick_draw_the_same_winner() -> None:
    first, second = player("a", MIDDLING), player("b", MIDDLING)
    assert winner(fake_world(9, 40), "dice-table", first, second) is winner(fake_world(9, 40), "dice-table", first, second)


def test_the_game_begins_only_once_both_have_sat_down() -> None:
    world = table_hall(guest("ada", (8, 8)), guest("bea", (12, 8)))
    sit_down(world, "ada", "dice-chair-1")
    advance(world, 2)
    assert (table(world)["game"]["players"], table(world)["game"]["ends_at"], happened(world, "dice_started")) == (["ada"], None, [])
    sit_down(world, "bea", "dice-chair-2")
    advance(world, 2)
    game = table(world)
    assert game["game"]["players"] == ["ada", "bea"]
    assert 20 < game["game"]["ends_at"] - world["time"] < RULES["game_seconds"]
    assert happened(world, "dice_started") == ["Ada and Bea sat down to a game of dice"] * 2


def test_neither_player_is_free_to_decide_during_the_game() -> None:
    world = two_players()
    advance(world, 5)
    assert [free_to_decide(world, who(world, name)) for name in ("ada", "bea")] == [False, False]
    assert [who(world, name)["status"] for name in ("ada", "bea")] == ["interacting", "interacting"]


def test_the_result_falls_after_the_game_with_one_winner_and_one_loser() -> None:
    world = two_players()
    advance(world, 6 + RULES["game_seconds"])
    won, lost = happened(world, "dice_won"), happened(world, "dice_lost")
    assert len(won) == len(lost) == 1 and won == lost
    assert table(world)["game"] is None
    assert [(who(world, name)["status"], who(world, name)["action"]) for name in ("ada", "bea")] == [("idle", None)] * 2


def test_the_players_remember_the_result_and_their_boredom_eases() -> None:
    world = two_players()
    advance(world, 6 + RULES["game_seconds"])
    kinds = {name: [item["kind"] for item in who(world, name)["thoughts"]] for name in ("ada", "bea")}
    assert sorted(item[-1] for item in kinds.values()) == ["lost_at_dice", "won_at_dice"]
    assert all(who(world, name)["needs"]["boredom"] < 30 for name in ("ada", "bea"))
    assert all(who(world, name)["needs"]["social"] < 60 for name in ("ada", "bea"))


def test_the_winner_is_named_in_the_log_as_the_one_who_beat_the_other() -> None:
    world = two_players()
    advance(world, 6 + RULES["game_seconds"])
    [message] = happened(world, "dice_won")
    assert message in ("Ada beat Bea at dice", "Bea beat Ada at dice")


def test_a_cheer_rings_out_at_the_win_but_never_loudly_enough_to_interrupt() -> None:
    assert EVENT_SOUNDS["dice_won"].loudness < default_rules()["attention"]["interrupt"]
    assert "dice_lost" not in EVENT_SOUNDS


def test_a_player_left_alone_gives_up_waiting_without_a_thought() -> None:
    world = table_hall(guest("ada", (8, 8)))
    sit_down(world, "ada", "dice-chair-1")
    advance(world, RULES["wait_seconds"] + 3)
    assert happened(world, "dice_abandoned") == ["Ada gave up waiting for a game of dice"]
    assert (table(world)["game"], who(world, "ada")["status"], who(world, "ada")["thoughts"]) == (None, "idle", [])
    assert who(world, "ada")["needs"]["boredom"] == pytest.approx(80, abs=10)


def test_taking_one_player_away_ends_the_game_for_the_other() -> None:
    world = two_players()
    advance(world, 8)
    assert start_action(world, "ada", {"id": "wait", "verb": "wait", "target_id": None})["accepted"]
    advance(world, 0.5)
    assert happened(world, "dice_abandoned") == ["Bea's game of dice broke off"]
    assert (table(world)["game"], who(world, "bea")["status"], who(world, "bea")["thoughts"]) == (None, "idle", [])
    assert happened(world, "dice_won") == []


def test_a_table_can_host_another_game_after_the_first() -> None:
    world = two_players()
    advance(world, 6 + RULES["game_seconds"])
    sit_down(world, "ada", "dice-chair-1")
    sit_down(world, "bea", "dice-chair-2")
    advance(world, 6 + RULES["game_seconds"])
    assert len(happened(world, "dice_won")) == 2


def test_the_same_seed_plays_the_same_game() -> None:
    results = []
    for _ in range(2):
        world = two_players()
        advance(world, 6 + RULES["game_seconds"])
        results.append(happened(world, "dice_won"))
    assert results[0] == results[1]


def test_a_sharp_sober_player_usually_beats_a_dull_drunk_one_in_a_played_game() -> None:
    room = {key: value for key, value in LAYOUT.items() if key != "arrival"}
    sharp_wins = 0
    for seed in range(40):
        world = create_world({**room, "actors": [guest("ada", (8, 8), SHARP), guest("bea", (12, 8), DULL)]}, seed=seed)
        who(world, "bea")["drunkenness"] = 0.6
        sit_down(world, "ada", "dice-chair-1")
        sit_down(world, "bea", "dice-chair-2")
        advance(world, 6 + RULES["game_seconds"])
        sharp_wins += happened(world, "dice_won") == ["Ada beat Bea at dice"]
    assert 25 <= sharp_wins <= 38


def test_a_save_made_mid_game_loads_back_unchanged() -> None:
    world = two_players()
    advance(world, 12)
    assert table(world)["game"] is not None
    assert parse_world(json.dumps(world)) == world


def test_a_save_made_while_one_player_waits_loads_back_unchanged() -> None:
    world = table_hall(guest("ada", (8, 8)))
    sit_down(world, "ada", "dice-chair-1")
    advance(world, 5)
    assert table(world)["game"]["ends_at"] is None
    assert parse_world(json.dumps(world)) == world


def mutated(change: Any) -> str:
    """A mid-game save with one thing changed in its dice table."""
    world = two_players()
    advance(world, 12)
    saved = deepcopy(world)
    change(saved, next(item for item in saved["map"]["objects"] if item["id"] == "dice-table"))
    return json.dumps(saved)


@pytest.mark.parametrize("change, message", [
    pytest.param(lambda world, item: item["game"]["players"].append("cid"), "game", id="three-players"),
    pytest.param(lambda world, item: item["game"].update(players=["ada", "ada"]), "game", id="the-same-player-twice"),
    pytest.param(lambda world, item: item["game"].update(players=["ada", "zed"]), "game", id="an-absent-player"),
    pytest.param(lambda world, item: item["game"].update(players=[]), "game", id="no-players"),
    pytest.param(lambda world, item: item["game"].update(ends_at=item["game"]["since"] - 1), "game", id="ends-before-it-began"),
    pytest.param(lambda world, item: item["game"].update(players=["ada"]), "game", id="ends-at-set-while-one-waits"),
    pytest.param(lambda world, item: item["game"].update(ends_at=None), "game", id="no-end-with-two-players"),
    pytest.param(lambda world, item: item["game"].update(since=world["time"] + 5), "game", id="began-in-the-future"),
    pytest.param(lambda world, item: item["game"].update(extra=1), "game", id="an-unknown-field"),
    pytest.param(lambda world, item: world["actors"][0].update(action=None), "game", id="a-player-who-is-not-playing"),
    pytest.param(lambda world, item: item.pop("game"), "game", id="a-dice-table-without-a-game-field"),
])
def test_a_malformed_game_fails_loudly(change: Any, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_world(mutated(change))


@pytest.mark.parametrize("change, message", [
    pytest.param(lambda rules: rules["skill"].update(luck=0.1), "dice", id="an-unknown-skill"),
    pytest.param(lambda rules: rules["skill"].update(patience=0.9), "dice", id="skill-weights-do-not-sum-to-one"),
    pytest.param(lambda rules: rules.update(drink=-0.1), "dice", id="negative-drink-weight"),
    pytest.param(lambda rules: rules.update(odds=[0.2, 0.7]), "dice", id="odds-not-round-a-half"),
    pytest.param(lambda rules: rules.update(odds=[0.8, 0.2]), "dice", id="odds-reversed"),
    pytest.param(lambda rules: rules.update(game_seconds=0), "dice", id="a-game-that-takes-no-time"),
    pytest.param(lambda rules: rules.update(wait_seconds=-1), "dice", id="a-negative-wait"),
    pytest.param(lambda rules: rules.pop("edge"), "dice", id="a-missing-rule"),
])
def test_saved_dice_rules_are_checked(change: Any, message: str) -> None:
    world = {"rules": default_rules()}
    change(world["rules"]["dice"])
    with pytest.raises(ValueError, match=message):
        check_rules(world)
