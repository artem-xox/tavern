"""Intentions in both runners: asked asynchronously, stale ones dropped, and followed by Jev's choices."""

import asyncio
from collections.abc import Mapping, Sequence
from pathlib import Path
from random import Random
from typing import Any

import pytest

from tavern.mind.agents import Evaluators
from tavern.app import create_default_app
from tavern.server.runtime import TavernRuntime
from tavern.mind.intentions import IntentionRules
from tavern.evening.lockstep import Pace, run_evening
from tavern.hall.world import create_world, start_action

RULES = IntentionRules(interval=180.0, min_gap=3.0)
HOMEWARD = "Go home before this turns ugly."


def chair(chair_id: str, x: int, y: int) -> dict[str, Any]:
    """Build a walkable chair at the table."""
    return {"id": chair_id, "kind": "chair", "name": f"Table · {chair_id}", "x": x, "y": y, "walkable": True,
            "table_id": "table", "interaction_spots": [[x, y]]}


def hall() -> dict[str, Any]:
    """A 10×6 hall with a two-chair table, a door, and Ada and Bea in their chairs."""
    return {"width": 10, "height": 6, "blocked": [], "objects": [
        {"id": "table", "kind": "table", "name": "Table", "x": 3, "y": 2, "width": 2, "height": 1},
        chair("west", 2, 2), chair("east", 5, 2),
        {"id": "door", "kind": "door", "name": "Door", "x": 0, "y": 5, "interaction_spots": [[0, 4]]},
    ], "actors": [{"id": "ada", "name": "Ada", "x": 2, "y": 2}, {"id": "bea", "name": "Bea", "x": 5, "y": 2}]}


def command(verb: str, target: str | None = None) -> dict[str, Any]:
    """Build an executable action."""
    return {"id": verb if target is None else f"{verb}:{target}", "verb": verb, "target_id": target}


def quarrelsome() -> dict[str, Any]:
    """Ada and Bea, seated, tipsy, impatient and each thinking ill of the other, talk; the first line is due at 5 s."""
    world = create_world(hall(), 4)
    for actor_id, seat in (("ada", "west"), ("bea", "east")):
        assert start_action(world, actor_id, command("sit", seat))["accepted"]
        actor = next(item for item in world["actors"] if item["id"] == actor_id)
        actor["needs"]["social"], actor["visit"]["beers"], actor["traits"]["patience"] = 100.0, 3, 0.0
        other = "bea" if actor_id == "ada" else "ada"
        actor["relations"][other] = {"name": other.title(), "opinion": -40.0, "familiarity": "acquaintance"}
        actor["knowledge"]["objects"]["door"] = {**world["map"]["objects"][3], "last_seen": 0.0}
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    world["conversations"][0]["next_turn_at"] = 5.0
    return world


async def complaining(view: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    """A fake turn writer: the speaker insults the other, who thinks ill of them, which ends in a quarrel."""
    other = next(item["id"] for item in view["conversation"]["participants"] if item["id"] != view["speaker"]["id"])
    return {"line": "This ale is piss, and so are you.", "act": "insult", "addressee": other, "topic": "the ale"}


def minding(asked: list[tuple[float, str, str]], clock: Any) -> Any:
    """A fake intender: after a quarrel the guest means to go home, otherwise to stay; notes each request."""
    async def intend(view: Mapping[str, Any]) -> dict[str, str]:
        asked.append((clock(), view["actor_id"], view["trigger"]["kind"]))
        if any(text.startswith("Quarreled") for text in view["thoughts"]):
            return {"thought": "Ada insulted me and my ale.", "intention": HOMEWARD}
        return {"thought": "A quiet evening.", "intention": "Stay seated and wait."}
    return intend


def _verbs(action: Mapping[str, Any]) -> set[str]:
    return {action["verb"], *(item["verb"] for item in action.get("members", []))}


async def following(view: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
                    config: Mapping[str, Any]) -> dict[str, float]:
    """A fake Jev: leave when the briefing states the homeward intention, otherwise wait."""
    wanted = "leave" if f"Their intention: {HOMEWARD.rstrip('.')}" in view["situation"] else "wait"
    return {action["id"]: float(wanted in _verbs(action)) for action in candidates}


def evening(intend: bool) -> tuple[list[dict[str, Any]], list[tuple[float, str, str]], dict[str, Any]]:
    """Play 30 s in lockstep with a one-second virtual latency; return events, intention requests, world."""
    world, asked = quarrelsome(), []
    intender = minding(asked, lambda: world["time"]) if intend else None
    result = asyncio.run(run_evening(world, {"typesafe_api_key": "fake", "temperature": 0.0}, Random(4),
                                     Evaluators(following, following), Pace(0.1, 1.0, 30.0), complaining,
                                     intender, RULES))
    return result.events, asked, world


def first(events: Sequence[Mapping[str, Any]], kind: str, actor_id: str, text: str = "") -> int:
    """Index of the first event of a kind by a guest whose message holds a text, or -1."""
    return next((index for index, event in enumerate(events) if event["type"] == kind
                 and event["actor_id"] == actor_id and text in event["message"]), -1)


def test_a_quarrel_changes_the_targets_intention_and_then_their_choice() -> None:
    events, _asked, _world = evening(intend=True)
    staying, quarrel = first(events, "intention", "bea", "Stay seated"), first(events, "quarrel", "bea")
    homeward, leaving = first(events, "intention", "bea", HOMEWARD), first(events, "action_started", "bea", "leave")
    assert -1 < staying < quarrel < homeward < leaving
    # The same evening without a mind: the quarrel happens, but Bea never means to go, and stays.
    offline = evening(intend=False)[0]
    assert first(offline, "quarrel", "bea") > -1 and first(offline, "action_started", "bea", "leave") == -1


def test_lockstep_asks_on_arrival_and_after_the_quarrel_one_latency_before_delivery() -> None:
    events, asked, _world = evening(intend=True)
    bea = [(round(time, 1), kind) for time, actor_id, kind in asked if actor_id == "bea"]
    assert bea[0] == (0.1, "arrival") and bea[1][1] == "quarrel"
    delivered = next(event for event in events if event["type"] == "intention" and event["actor_id"] == "bea")
    assert round(delivered["time"], 1) == 1.1


def test_lockstep_intentions_replay_identically() -> None:
    assert evening(intend=True)[0] == evening(intend=True)[0]


def test_offline_evenings_write_no_intentions() -> None:
    events, asked, world = evening(intend=False)
    assert (asked, [event for event in events if event["type"].startswith("intention")],
            [item["intention"] for item in [*world["actors"], *world["departed"]]]) == ([], [], [None, None])


def test_live_runtime_asks_the_mind_without_blocking(tmp_path: Path) -> None:
    async def run() -> tuple[list[Any], dict[str, Any]]:
        asked: list[tuple[float, str, str]] = []
        runtime = TavernRuntime(hall(), tmp_path / "save.json", {"temperature": 0.0},
                                intender=minding(asked, lambda: runtime.world["time"]), intention_rules=RULES)
        snapshot = runtime.snapshot()
        for _ in range(3):
            runtime.advance(0.1)
            for _ in range(3):
                await asyncio.sleep(0)
        intentions = [item["intention"]["intention"] for item in runtime.world["actors"]]
        await runtime.close()
        return intentions, snapshot["ai"]
    intentions, ai = asyncio.run(run())
    assert (intentions, ai["intentions"]) == (["Stay seated and wait."] * 2, True)


def test_live_runtime_without_a_mind_labels_intentions_off(tmp_path: Path) -> None:
    runtime = TavernRuntime(hall(), tmp_path / "save.json", {"temperature": 0.0})
    assert runtime.snapshot()["ai"]["intentions"] is False


@pytest.mark.parametrize("key, expected", [
    pytest.param("test-key", True, id="claude-key-gives-intentions"),
    pytest.param("", False, id="empty-key-is-offline"),
])
def test_default_server_writes_intentions_only_with_a_claude_key(
        monkeypatch: pytest.MonkeyPatch, key: str, expected: bool) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", key)
    monkeypatch.delenv("TAVERN_DATABASE_ENABLED", raising=False)
    runtime = create_default_app().state.sessions.open("device-test")
    assert runtime.snapshot()["ai"]["intentions"] is expected


def test_the_shared_prefix_is_long_enough_to_cache() -> None:
    # Haiku 4.5 caches prefixes of 4096 tokens or more; English runs about 4 characters a token,
    # and the live token counter gave this file about 5,100.
    prefix = (Path(__file__).resolve().parents[1] / "data" / "minds" / "intention_prefix.md").read_text()
    assert len(prefix) >= 4096 * 4
