"""The fight metrics: what an evening's fights came to, read from the fights and the event log."""

from typing import Any

import pytest

from tavern.evening.fight_metrics import fight_counts

NAMES = {"ada": "Ada", "bea": "Bea", "cid": "Cid"}


def fight(a: str = "ada", b: str = "bea", outcome: str | None = "knockout", loser: str | None = "bea",
          cause: str = "drink", hits: int = 3, swings: int = 4, ended_at: float | None = 15.0) -> dict[str, Any]:
    return {"id": "fight-1", "a": a, "b": b, "weapons": {a: "fists", b: "cudgel"}, "started_at": 10.0,
            "next_exchange_at": 11.0, "exchanges": [{"time": 11.0 + index, "attacker": a, "hit": index < hits, "damage": 5.0}
                                                    for index in range(swings * 2)],
            "waiting": [], "witnessed": True, "cause": cause, "outcome": outcome, "loser": loser, "ended_at": ended_at}


def event(kind: str, message: str, time: float = 20.0) -> dict[str, Any]:
    return {"type": kind, "message": message, "time": time, "actor_id": "ada"}


def test_no_fights_is_an_empty_count() -> None:
    assert fight_counts([], [], NAMES) == {"count": 0, "fights": [], "outcomes": {}, "causes": {}, "reactions": {
        "watch_fight": 0, "cheer": 0, "intervene": 0, "join_fight": 0, "help_up": 0},
        "tended": 0, "refused": 0, "limped_home": 0}


def test_a_fight_is_told_by_name_with_its_winner_and_length() -> None:
    record = fight_counts([fight()], [], NAMES)["fights"][0]
    assert (record["a"], record["b"], record["winner"], record["seconds"], record["exchanges"], record["hits"],
            record["weapons"], record["cause"]) == ("Ada", "Bea", "Ada", 5.0, 4, 3, {"Ada": "fists", "Bea": "cudgel"}, "drink")


@pytest.mark.parametrize("fights, outcomes, causes", [
    pytest.param([fight(), fight(outcome="parted", loser=None, cause="hatred")], {"knockout": 1, "parted": 1},
                 {"drink": 1, "hatred": 1}, id="two-different"),
    pytest.param([fight(), fight()], {"knockout": 2}, {"drink": 2}, id="duplicates"),
    pytest.param([fight(outcome=None, loser=None, ended_at=None)], {}, {"drink": 1}, id="still-running"),
])
def test_outcomes_and_causes_are_counted(fights: list[dict[str, Any]], outcomes: dict[str, int], causes: dict[str, int]) -> None:
    counts = fight_counts(fights, [], NAMES)
    assert (counts["outcomes"], counts["causes"]) == (outcomes, causes)


def test_reactions_and_treatment_are_counted_from_the_events() -> None:
    events = [event("action_started", "Cid chose cheer"), event("action_started", "Cid chose cheer", 30.0),
              event("action_started", "Cid chose intervene"), event("action_started", "Cid chose sit"),
              event("tended", "Ada took Bea's remedy and looks better already"),
              event("tended", "Ada took Bea's remedy and looks better already"),
              event("remedy_refused", "Bea would not give Ada a remedy"), event("limped_home", "Ada slipped out")]
    counts = fight_counts([], events, NAMES)
    assert (counts["reactions"]["cheer"], counts["reactions"]["intervene"], counts["tended"], counts["refused"],
            counts["limped_home"]) == (2, 1, 1, 1, 1)


def test_an_unknown_fighter_fails_loudly() -> None:
    with pytest.raises(KeyError):
        fight_counts([fight(a="zed")], [], NAMES)
