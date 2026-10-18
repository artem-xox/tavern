"""Matches at the dart boards: two guests throwing side by side, and who wins."""

from collections.abc import Mapping
from typing import Any

from tavern.hall.chance import roll
from tavern.hall.memory import record_event
from tavern.hall.state import Actor, DiceRules, World
from tavern.social.dice import win_chance as dice_chance
from tavern.social.names import called
from tavern.social.thoughts import think

PLAY = "play_darts"


def win_chance(first: Mapping[str, Any], second: Mapping[str, Any], rules: DiceRules,
               edge: float = 1.0, odds: tuple[float, float] = (0.1, 0.9)) -> float:
    """Tell the first player's chance to win a match of darts.

    Darts are played with the dice's form (traits less drink), but skill tells more than at dice: a
    steadier hand moves the chance twice as far and luck is left a tenth either way.

    Args:
        first: Visitor with `traits` and `drunkenness`.
        second: Their opponent.
        rules: Dice rules, whose `skill` and `drink` weights give the form.
        edge: How far the gap in form moves the chance off 0.5 (dice: 0.5).
        odds: Bounds of the chance, symmetric round a half (dice: 0.2 and 0.8).

    Returns:
        The first player's chance, within `odds`.

    Raises:
        ValueError: A trait or drunkenness is out of range.
    """
    return dice_chance(first, second, {**rules, "edge": edge, "odds": list(odds)})


def settle_match(world: World, actor: Actor, board: Mapping[str, Any], overlap: float = 3.0) -> None:
    """Match a guest finishing their throws against whoever threw beside them, if anyone did.

    The first of the two to finish settles it: the other must have been throwing at the other board
    for `overlap` seconds, and not have settled a match already during these throws. The winner is
    drawn, the same on a replay, and both remember it.

    Args:
        world: World whose event log and the players' thoughts are updated in place.
        actor: Visitor whose throws have run out.
        board: The board they threw at.
        overlap: Seconds a neighbour must have been throwing to count as an opponent.
    """
    neighbour = _neighbour(world, actor, board, overlap)
    if neighbour is None:
        return
    first, second = sorted((actor, neighbour), key=lambda item: item["id"])
    chance = win_chance(first, second, world["rules"]["dice"])
    champion = first if roll(world, "darts", board["id"], first["id"], second["id"]) < chance else second
    loser = second if champion is first else first
    message = f"{champion['name']} beat {loser['name']} at darts"
    record_event(world, champion, "darts_won", message)
    record_event(world, loser, "darts_lost", message)
    think(champion, "won_at_darts", world["time"], f"Beat {called(champion, loser)} at darts", message, about=loser)
    think(loser, "lost_at_darts", world["time"], f"Lost to {called(loser, champion)} at darts", message, about=champion)


def _neighbour(world: Mapping[str, Any], actor: Actor, board: Mapping[str, Any], overlap: float) -> Actor | None:
    boards = {item["id"] for item in world["map"]["objects"] if item["kind"] == board["kind"] and item["id"] != board["id"]}
    length = world["rules"]["durations"][PLAY]
    for other in world["actors"]:
        action = other["action"]
        if (action and action["verb"] == PLAY and action["target_id"] in boards and other["status"] == "interacting"
                and length - other["_remaining"] >= overlap
                and not _matched_since(world, other, world["time"] - (length - other["_remaining"]))):
            return other
    return None


def _matched_since(world: Mapping[str, Any], actor: Mapping[str, Any], since: float) -> bool:
    return any(item["type"] in ("darts_won", "darts_lost") and item["time"] >= since for item in actor["memory"])
