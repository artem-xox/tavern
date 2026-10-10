"""What an evening's fights came to: how they started and ended, how the room reacted, and how the hurt were mended."""

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

# The verbs of the room's reactions (`tavern.social.bystanders`) as they show in "X chose <verb>" events.
REACTIONS = ("watch_fight", "cheer", "intervene", "join_fight", "help_up")


class FightRecord(TypedDict):
    """One fight: who, with what, what brought it on, how long it lasted, its swings and hits, how it ended, who won."""

    a: str
    b: str
    weapons: dict[str, str]
    cause: str
    seconds: float | None
    exchanges: int
    hits: int
    outcome: str | None
    winner: str | None


class FightCounts(TypedDict):
    """The fights of an evening, with outcomes and causes counted, the reactions by verb, and how the hurt fared."""

    count: int
    fights: list[FightRecord]
    outcomes: dict[str, int]
    causes: dict[str, int]
    reactions: dict[str, int]
    tended: int
    refused: int
    limped_home: int


def fight_counts(fights: Sequence[Mapping[str, Any]], events: Sequence[Mapping[str, Any]],
                 names: Mapping[str, str]) -> FightCounts:
    """Summarise an evening's fights.

    Args:
        fights: The world's `fights`, finished or not.
        events: The complete event log: `action_started` for each reaction, `tended` (logged for the giver and the
            receiver, so counted once per time and message), `remedy_refused` and `limped_home`.
        names: Every guest's name by ID, in the hall and gone.

    Returns:
        A record per fight, counts of outcomes and causes (a fight still running counts under no outcome), and:
        `reactions` per verb of the room's, `tended` (remedies that mended someone), `refused` (a healer turned someone
        away, once per event time and message) and `limped_home` (knocked out, untreated, slipped away).

    Raises:
        KeyError: A fighter is missing from `names`.
    """
    records: list[FightRecord] = []
    outcomes: dict[str, int] = {}
    causes: dict[str, int] = {}
    for fight in fights:
        winner = None
        if fight["loser"] is not None:
            winner = fight["b"] if fight["loser"] == fight["a"] else fight["a"]
        records.append(FightRecord(
            a=names[fight["a"]], b=names[fight["b"]], weapons={names[key]: kind for key, kind in fight["weapons"].items()},
            cause=fight["cause"], seconds=None if fight["ended_at"] is None else fight["ended_at"] - fight["started_at"],
            exchanges=len(fight["exchanges"]) // 2, hits=sum(1 for item in fight["exchanges"] if item["hit"]),
            outcome=fight["outcome"], winner=None if winner is None else names[winner]))
        if fight["outcome"] is not None:
            outcomes[fight["outcome"]] = outcomes.get(fight["outcome"], 0) + 1
        causes[fight["cause"]] = causes.get(fight["cause"], 0) + 1
    reactions = {verb: sum(1 for event in events if event["type"] == "action_started"
                           and event["message"].endswith(f" chose {verb}")) for verb in REACTIONS}
    once = lambda kind: len({(event["time"], event["message"]) for event in events if event["type"] == kind})  # noqa: E731
    return {"count": len(records), "fights": records, "outcomes": outcomes, "causes": causes, "reactions": reactions,
            "tended": once("tended"), "refused": once("remedy_refused"),
            "limped_home": sum(1 for event in events if event["type"] == "limped_home")}
