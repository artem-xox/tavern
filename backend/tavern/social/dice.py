"""Games of dice: who sits at the dice table, when the result falls, and who wins.

A dice table (`room.OBJECT_KINDS`) keeps its game in `game`: None, or `{"players", "since", "ends_at"}`.
Guests get there through `play_dice`, an ordinary action sent by an accepted `dice_together` invitation
(`tavern.social.invitations`). The game, not the action's timer, ends the action: `settle_games` runs
once a tick and tells the world whom to finish and whom to release.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any

from tavern.hall.chance import roll
from tavern.hall.memory import record_event
from tavern.hall.room import find_object
from tavern.hall.state import Actor, DiceRules, World
from tavern.hall.validation import number
from tavern.mind.cards import PARAMS
from tavern.social.names import called
from tavern.social.thoughts import think

PLAY = "play_dice"
_GAME_FIELDS = {"players", "since", "ends_at"}


@dataclass(frozen=True)
class Settled:
    """What a tick's games left to the world: players whose game was played out, and players whose game was
    broken off or never began. The world completes the first and clears the second."""

    done: list[Actor]
    released: list[Actor]


def form(actor: Mapping[str, Any], rules: DiceRules) -> float:
    """Tell how well a guest plays tonight: their traits, less what the ale takes away.

    Args:
        actor: Visitor with `traits` and `drunkenness`. A trait they lack counts as 0.5, as
            tolerance does for the ale.
        rules: Dice rules: the `skill` weights and the `drink` weight.

    Returns:
        The weighted traits (0–1 when the weights sum to 1) minus `drink` × drunkenness.

    Raises:
        ValueError: A trait or their drunkenness is not a number from 0 to 1.
    """
    skill = sum(weight * number(actor["traits"].get(name, 0.5), name, 0, 1) for name, weight in rules["skill"].items())
    return skill - rules["drink"] * number(actor["drunkenness"], "Drunkenness", 0, 1)


def win_chance(first: Mapping[str, Any], second: Mapping[str, Any], rules: DiceRules) -> float:
    """Tell the first player's chance to win.

    Args:
        first: Visitor who sat down first.
        second: Visitor who sat down second.
        rules: Dice rules: `edge` and the `odds` bounds.

    Returns:
        0.5 plus `edge` × the gap in form, kept within `odds` so luck always counts. The bounds are
        symmetric, so the two seats' chances add up to one.

    Raises:
        ValueError: A trait or drunkenness is out of range (see `form`).
    """
    low, high = rules["odds"]
    return min(high, max(low, 0.5 + rules["edge"] * (form(first, rules) - form(second, rules))))


def winner(world: World, table_id: str, first: Actor, second: Actor) -> Actor:
    """Draw who wins a game.

    Args:
        world: World with the seed, tick and dice rules; the draw is seeded by the evening, tick, table
            and players, so a replay or a reloaded save throws the same.
        table_id: The dice table.
        first: Visitor who sat down first; they win when the draw falls below their chance.
        second: Visitor who sat down second.

    Returns:
        The winner, one of the two.
    """
    chance = win_chance(first, second, world["rules"]["dice"])
    return first if roll(world, "dice", table_id, first["id"], second["id"]) < chance else second


def open_chairs(world: Mapping[str, Any], table_id: str) -> list[str]:
    """Tell which chairs of a dice table two guests could take now.

    Args:
        world: Current world.
        table_id: A dice table.

    Returns:
        Its first two chairs in map order when no game is under way and neither is reserved
        (the walk to one reserves it), else an empty list.

    Raises:
        ValueError: The ID is no dice table.
    """
    table = find_object(world["map"], table_id)
    if table is None or table["kind"] != "dice_table":
        raise ValueError(f"{table_id!r} is not a dice table")
    chairs = [item for item in world["map"]["objects"] if item["kind"] == "dice_chair" and item["table_id"] == table_id]
    free = table["game"] is None and len(chairs) >= 2 and all(item["reserved_by"] is None for item in chairs)
    return [item["id"] for item in chairs[:2]] if free else []


def settle_games(world: World) -> Settled:
    """Move every dice table's game one step further.

    A guest who has reached a dice chair joins the game; the second to sit starts the clock. A game
    whose player has been taken away (to another action) ends for the other, and a player left alone for
    `wait_seconds` gives up. When the clock runs out a winner is drawn; both players remember it.

    Args:
        world: World whose dice tables, event log and players' thoughts are updated in place.

    Returns:
        The players to finish and the players to release; the caller completes and clears their actions.

    Raises:
        ValueError: More than two guests sit at one table, or a player's form is out of range.
    """
    done: list[Actor] = []
    released: list[Actor] = []
    for table in world["map"]["objects"]:
        if table["kind"] == "dice_table":
            _settle(world, table, done, released)
    return Settled(done, released)


def _settle(world: World, table: dict[str, Any], done: list[Actor], released: list[Actor]) -> None:
    seated = _seated(world, table)
    game = table["game"]
    if game is not None and not set(game["players"]) <= {item["id"] for item in seated}:
        released.extend(_break_off(world, table, seated))
        return
    if game is None and not seated:
        return
    game = table["game"] = game or {"players": [], "since": world["time"], "ends_at": None}
    game["players"] += [item["id"] for item in seated if item["id"] not in game["players"]]
    if len(game["players"]) > 2:
        raise ValueError(f"{len(game['players'])} guests sit at {table['name']}, which has two chairs")
    players = [next(item for item in seated if item["id"] == identifier) for identifier in game["players"]]
    _run_clock(world, table, players, done, released)


def _break_off(world: World, table: dict[str, Any], seated: list[Actor]) -> list[Actor]:
    # A player was taken away (or never reached the game): whoever still sits is released.
    staying = [item for item in seated if item["id"] in table["game"]["players"]]
    for actor in staying:
        record_event(world, actor, "dice_abandoned", f"{actor['name']}'s game of dice broke off")
    table["game"] = None
    return staying


def _run_clock(world: World, table: dict[str, Any], players: list[Actor], done: list[Actor],
               released: list[Actor]) -> None:
    rules, now, game = world["rules"]["dice"], world["time"], table["game"]
    if len(players) == 2 and game["ends_at"] is None:
        game["ends_at"] = now + rules["game_seconds"]
        for actor in players:
            record_event(world, actor, "dice_started", f"{players[0]['name']} and {players[1]['name']} sat down to a game of dice")
    if game["ends_at"] is None and now - game["since"] >= rules["wait_seconds"]:
        record_event(world, players[0], "dice_abandoned", f"{players[0]['name']} gave up waiting for a game of dice")
        released.append(players[0])
        table["game"] = None
    elif game["ends_at"] is not None and now >= game["ends_at"]:
        _throw(world, table, players[0], players[1])
        done.extend(players)
        table["game"] = None


def _seated(world: Mapping[str, Any], table: Mapping[str, Any]) -> list[Actor]:
    # Guests who have reached one of the table's chairs to play, in world order.
    chairs = {item["id"] for item in world["map"]["objects"]
              if item["kind"] == "dice_chair" and item["table_id"] == table["id"]}
    return [item for item in world["actors"] if item["action"] and item["action"]["verb"] == PLAY
            and item["action"]["target_id"] in chairs and item["status"] == "interacting"]


def _throw(world: World, table: Mapping[str, Any], first: Actor, second: Actor) -> None:
    champion = winner(world, table["id"], first, second)
    loser = second if champion is first else first
    message = f"{champion['name']} beat {loser['name']} at dice"
    record_event(world, champion, "dice_won", message)
    record_event(world, loser, "dice_lost", message)
    think(champion, "won_at_dice", world["time"], f"Beat {called(champion, loser)} at dice", message, about=loser)
    think(loser, "lost_at_dice", world["time"], f"Lost to {called(loser, champion)} at dice", message, about=champion)


def check_saved_games(world: Mapping[str, Any]) -> None:
    """Check the games saved on a world's dice tables.

    Args:
        world: Decoded save with checked actors and map.

    Raises:
        ValueError: A dice table lacks `game`, or a game is malformed: not exactly its fields, no or
            more than two players, a repeated or absent player, one who is not playing at that table, a
            start in the future, an end before the start, or an end set exactly when only one waits.
    """
    chairs = {item["id"]: item["table_id"] for item in world["map"]["objects"] if item["kind"] == "dice_chair"}
    people = {item["id"]: item for item in world["actors"]}
    for table in (item for item in world["map"]["objects"] if item["kind"] == "dice_table"):
        if "game" not in table:
            raise ValueError(f"Saved dice table {table['id']!r} has no game field")
        if table["game"] is not None:
            _check_game(table["game"], table, world, chairs, people)


def _check_game(game: Any, table: Mapping[str, Any], world: Mapping[str, Any], chairs: Mapping[str, str],
                people: Mapping[str, Any]) -> None:
    label = f"Invalid saved game at {table['id']!r}"
    if not isinstance(game, dict) or set(game) != _GAME_FIELDS:
        raise ValueError(f"{label}: expected {sorted(_GAME_FIELDS)}")
    players = game["players"]
    if not isinstance(players, list) or not 1 <= len(players) <= 2 or len(set(players)) != len(players):
        raise ValueError(f"{label}: one or two distinct players")
    for identifier in players:
        action = people[identifier]["action"] if identifier in people else None
        if action is None or action["verb"] != PLAY or chairs.get(action["target_id"]) != table["id"]:
            raise ValueError(f"{label}: {identifier!r} is not playing at it")
    since = number(game["since"], "Saved game start", 0, world["time"])
    if (game["ends_at"] is None) != (len(players) == 1):
        raise ValueError(f"{label}: it ends exactly once two have sat down")
    if game["ends_at"] is not None:
        number(game["ends_at"], "Saved game end", since, math.inf)


def check_dice_rules(dice: Any) -> None:
    """Check the dice rules saved with a world.

    Args:
        dice: Decoded `rules.dice`: `skill` weights over card params that sum to 1, non-negative `drink`
            and `edge`, `odds` bounds symmetric round a half, and positive `game_seconds` and
            `wait_seconds`.

    Raises:
        ValueError: A rule is missing, unknown or out of range.
    """
    keys = {"skill", "drink", "edge", "odds", "game_seconds", "wait_seconds"}
    if not isinstance(dice, dict) or set(dice) != keys:
        raise ValueError("Invalid saved dice rules")
    skill = dice["skill"]
    if not isinstance(skill, dict) or not skill or not set(skill) <= set(PARAMS):
        raise ValueError(f"Saved dice skill must weigh card params, not {sorted(skill) if isinstance(skill, dict) else skill!r}")
    weights = [number(weight, f"Saved dice weight {name}", 0, 1) for name, weight in skill.items()]
    if not math.isclose(sum(weights), 1.0):
        raise ValueError("Saved dice skill weights must sum to 1")
    for key in ("drink", "edge"):
        number(dice[key], f"Saved dice rule {key}", 0, math.inf)
    _check_odds(dice["odds"])
    for key in ("game_seconds", "wait_seconds"):
        if not 0 < number(dice[key], f"Saved dice rule {key}", 0, math.inf):
            raise ValueError(f"Saved dice rule {key} must be above zero")


def _check_odds(odds: Any) -> None:
    if not isinstance(odds, Sequence) or isinstance(odds, str) or len(odds) != 2:
        raise ValueError("Saved dice odds must be a low and a high bound")
    low, high = (number(item, "Saved dice odds", 0, 1) for item in odds)
    if not 0 < low < high or not math.isclose(low + high, 1.0):
        raise ValueError("Saved dice odds must be symmetric round a half, with luck counting (0 < low < high)")
