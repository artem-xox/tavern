"""The player section of an evening's metrics, from the events the player's path logs."""

from typing import Any

import pytest

from tavern.evening.player_metrics import player_counts


def turn(act: str, player: bool = True) -> dict[str, Any]:
    event = {"type": "turn", "actor_id": "monroe", "act": act, "message": "..."}
    return {**event, "player": True} if player else event


def event(kind: str, message: str = "...") -> dict[str, Any]:
    return {"type": kind, "actor_id": "monroe", "message": message}


def act(verb: str) -> dict[str, Any]:
    return {**event("player_act"), "verb": verb}


def refusal(kind: str) -> dict[str, Any]:
    return {"type": "control", "actor_id": None, "message": f"Player script: {kind} refused: nope"}


def test_an_evening_without_a_player_has_no_section() -> None:
    assert player_counts([turn("remark", player=False)], None) is None


def test_an_evening_with_a_player_who_did_nothing_counts_zeros() -> None:
    assert player_counts([], "monroe") == {"actor": "monroe", "lines": {}, "misread": 0, "silences": 0, "ignored": 0,
                                           "actions": {}, "refused": 0}


def test_the_section_counts_the_players_events() -> None:
    events = [turn("flatter"), turn("flatter"), turn("insult"), turn("silence"), turn("remark", player=False),
              event("misread"), event("ignored"), event("ignored"), act("take_beer"), act("take_beer"), act("sit"),
              refusal("act"), event("steer"), {"type": "control", "actor_id": None, "message": "Decision failed"}]
    assert player_counts(events, "monroe") == {
        "actor": "monroe", "lines": {"flatter": 2, "insult": 1}, "misread": 1, "silences": 1, "ignored": 2,
        "actions": {"take_beer": 2, "sit": 1}, "refused": 1}
