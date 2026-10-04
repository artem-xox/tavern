"""Agreeing to play dice: the invitation, the answer, the walk to the table and the game that follows."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
from random import Random
from typing import Any

import pytest

from tavern.adapters.persistence import load_world, save_world
from tavern.evening.lockstep import Pace, run_evening
from tavern.evening.metrics import dice_metrics
from tavern.evening.scenario import open_evening, parse_scenario
from tavern.hall.world import create_world, start_action
from tavern.mind.agents import Evaluators
from tavern.mind.cards import parse_cards
from tavern.mind.haiku_turns import turn_content, turn_question
from tavern.mind.scripted import scripted_turn
from tavern.social.dice import open_chairs
from tavern.social.invitations import KINDS, offered_kinds
from tavern.social.turns import turn_view
from social_hall import actor, advance, command, hall, know, say, scene_of

ROOT = Path(__file__).resolve().parents[1]
TABLE = {"id": "dice-table", "kind": "dice_table", "name": "Dice table", "x": 7, "y": 4,
         "interaction_spots": [[7, 3], [7, 5]]}
CHAIRS = [{"id": f"dice-chair-{number}", "kind": "dice_chair", "name": f"Dice table · {side}", "x": x, "y": 4,
           "walkable": True, "table_id": "dice-table", "facing": facing, "interaction_spots": [[x, 4]]}
          for number, side, x, facing in ((1, "west", 6, "east"), (2, "east", 8, "west"))]


def dice_talk(social: float = 95.0) -> dict[str, Any]:
    """Ada and Bea sit at the near table talking, with a dice table across the hall that Ada has seen."""
    data = hall()
    data["objects"] += [deepcopy(TABLE), *deepcopy(CHAIRS)]
    world = create_world(data, 4)
    for actor_id, seat in (("ada", "w"), ("bea", "e")):
        assert start_action(world, actor_id, command("sit", seat))["accepted"]
    for item in world["actors"]:
        item["needs"]["social"] = social
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    know(world, "ada", "dice-table")
    return world


def table(world: dict[str, Any]) -> dict[str, Any]:
    """The dice table."""
    return next(item for item in world["map"]["objects"] if item["id"] == "dice-table")


def chair(world: dict[str, Any], chair_id: str) -> dict[str, Any]:
    """A dice chair."""
    return next(item for item in world["map"]["objects"] if item["id"] == chair_id)


def invite_to_dice(world: dict[str, Any], answer: str = "accept") -> None:
    """Ada invites Bea to a game of dice, and Bea answers."""
    say(world, "invite", "A game of dice?", invitation="dice_together")
    say(world, answer, "Gladly." if answer == "accept" else "Not tonight.")


def doing(world: dict[str, Any]) -> list[tuple[str | None, str | None]]:
    """What Ada and Bea are doing, as (verb, target)."""
    return [((actor(world, name)["action"] or {}).get("verb"), (actor(world, name)["action"] or {}).get("target_id"))
            for name in ("ada", "bea")]


def happened(world: dict[str, Any], kind: str) -> list[str]:
    """The messages of logged events of a kind."""
    return [event["message"] for event in world["events"] if event["type"] == kind]


@pytest.mark.parametrize("prepare, expected", [
    pytest.param(lambda world: None, ["dice-chair-1", "dice-chair-2"], id="a-free-table"),
    pytest.param(lambda world: table(world).update(game={"players": ["ada"], "since": 0.0, "ends_at": None}), [],
                 id="a-game-under-way"),
    pytest.param(lambda world: chair(world, "dice-chair-2").update(reserved_by="cid"), [], id="a-chair-taken"),
    pytest.param(lambda world: chair(world, "dice-chair-1").update(reserved_by="cid"), [], id="the-other-chair-taken"),
])
def test_the_open_chairs_of_a_dice_table(prepare: Any, expected: list[str]) -> None:
    world = dice_talk()
    prepare(world)
    assert open_chairs(world, "dice-table") == expected


def test_asking_for_the_chairs_of_something_that_is_no_dice_table_fails_loudly() -> None:
    with pytest.raises(ValueError, match="dice table"):
        open_chairs(dice_talk(), "near")


@pytest.mark.parametrize("prepare, offered", [
    pytest.param(lambda world: None, True, id="a-free-table-she-knows"),
    pytest.param(lambda world: actor(world, "ada")["knowledge"]["objects"].pop("dice-table"), False,
                 id="no-table-she-knows"),
    pytest.param(lambda world: table(world).update(game={"players": ["cid"], "since": 0.0, "ends_at": None}), False,
                 id="a-game-under-way"),
    pytest.param(lambda world: chair(world, "dice-chair-1").update(reserved_by="cid"), False, id="a-chair-reserved"),
])
def test_dice_are_offered_to_a_guest_who_knows_a_free_table(prepare: Any, offered: bool) -> None:
    world = dice_talk()
    prepare(world)
    assert ("dice_together" in offered_kinds(world, scene_of(world), actor(world, "ada"))) is offered


def test_accepting_sends_the_two_to_different_chairs_of_the_table() -> None:
    world = dice_talk()
    invite_to_dice(world)
    assert doing(world) == [("play_dice", "dice-chair-1"), ("play_dice", "dice-chair-2")]
    assert (scene_of(world), world["invitations"]) == (None, [])


def test_the_two_walk_over_and_play_to_a_result() -> None:
    world = dice_talk()
    invite_to_dice(world)
    advance(world, 40)
    assert len(happened(world, "dice_started")) == 2 and len(happened(world, "dice_won")) == 1
    assert (table(world)["game"], doing(world)) == (None, [(None, None), (None, None)])


def test_a_declined_game_changes_nothing() -> None:
    world = dice_talk()
    before = doing(world)
    invite_to_dice(world, answer="decline")
    assert (doing(world), world["invitations"], table(world)["game"]) == (before, [], None)


def test_a_table_taken_before_the_answer_fails_the_errand() -> None:
    world = dice_talk()
    say(world, "invite", "A game of dice?", invitation="dice_together")
    chair(world, "dice-chair-1").update(reserved_by="cid")
    say(world, "accept", "Gladly.")
    assert happened(world, "invitation_failed") == ["Ada and Bea could not play a game of dice"]
    assert world["invitations"] == [] and "play_dice" not in [verb for verb, _ in doing(world)]
    assert table(world)["game"] is None


def test_a_pending_dice_invitation_survives_a_save(tmp_path: Path) -> None:
    world = dice_talk()
    say(world, "invite", "A game of dice?", invitation="dice_together")
    save_world(world, tmp_path / "save.json")
    assert load_world(tmp_path / "save.json")["conversations"][0]["invitation"] == {
        "kind": "dice_together", "from": "ada", "to": "bea"}


def test_the_invitation_is_one_of_the_kinds_the_turn_schema_allows() -> None:
    schema = turn_question(turn_view(dice_talk(), scene_of(dice_talk())))["schema"]
    assert "dice_together" in KINDS and "dice_together" in schema["properties"]["invitation"]["anyOf"][0]["enum"]


def writer_view(boredom: float, courage: float, kinds: list[str]) -> dict[str, Any]:
    """Ada's view of her next line in the dice scene, with nothing yet to tell, bored as given."""
    world = dice_talk()
    say(world, "greet", "Evening.")
    say(world, "small_talk", "Cold tonight.")
    view = turn_view(world, scene_of(world))
    view["speaker"]["places"] = []
    view["speaker"]["needs"].update(boredom=boredom, social=90.0)
    view["speaker"]["traits"]["courage"] = courage
    view["invitations"] = kinds
    return view


def invited_to(view: dict[str, Any]) -> set[str]:
    """The kinds the scripted writer invites to over many seeds."""
    results = [scripted_turn({**view, "seed": seed}) for seed in range(80)]
    return {item["invitation"] for item in results if item["act"] == "invite"}


@pytest.mark.parametrize("boredom, courage, kinds, expected", [
    pytest.param(70, 0.8, ["darts_together", "dice_together"], {"dice_together"}, id="bored-and-bold-throws-dice"),
    pytest.param(70, 0.2, ["darts_together", "dice_together"], {"darts_together"}, id="bored-and-timid-throws-darts"),
    pytest.param(70, 0.8, ["darts_together"], {"darts_together"}, id="no-dice-table-so-darts"),
    pytest.param(70, 0.8, ["dice_together"], {"dice_together"}, id="only-dice-on-offer"),
    pytest.param(20, 0.8, ["dice_together"], set(), id="not-bored-no-dice"),
])
def test_the_scripted_writer_invites_the_bold_and_bored_to_dice(boredom: float, courage: float, kinds: list[str],
                                                                expected: set[str]) -> None:
    assert invited_to(writer_view(boredom, courage, kinds)) == expected


def pending_dice(**needs: float) -> dict[str, Any]:
    """Bea's view of Ada's invitation to dice, with some of Bea's needs set."""
    world = dice_talk()
    say(world, "invite", "Dice?", invitation="dice_together")
    view = turn_view(world, scene_of(world))
    view["speaker"]["needs"].update(needs)
    return view


@pytest.mark.parametrize("needs, act", [
    pytest.param({"boredom": 60}, "accept", id="bored-guest-plays"),
    pytest.param({"boredom": 5}, "decline", id="content-guest-declines"),
])
def test_the_scripted_invitee_answers_a_dice_invitation_by_boredom(needs: dict[str, float], act: str) -> None:
    assert scripted_turn(pending_dice(**needs))["act"] == act


@pytest.mark.parametrize("boredom, kinds, nudged", [
    pytest.param(70, ["dice_together"], True, id="bored-with-a-table-free"),
    pytest.param(70, ["darts_together"], False, id="bored-without-a-table"),
    pytest.param(20, ["dice_together"], False, id="not-bored"),
    pytest.param(50, ["dice_together", "buy_drink"], True, id="bored-just-enough"),
])
def test_haiku_is_told_when_the_dice_table_stands_free_for_a_bored_guest(boredom: float, kinds: list[str],
                                                                         nudged: bool) -> None:
    content = turn_content(writer_view(boredom, 0.5, kinds))
    assert ("dice table stands free" in content) is nudged


async def never_asked(*arguments: Any) -> dict[str, float]:
    """A Jev that must not be asked: this evening runs on the local policy."""
    raise AssertionError("Jev must not be asked in an offline evening")


async def dicing_writer(view: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """A turn writer that invites to dice whenever it can and accepts any invitation, else scripted."""
    scene, me = view["conversation"], view["speaker"]
    pending = scene["invitation"]
    if pending and pending["to"] == me["id"]:
        return {"line": "Gladly.", "act": "accept", "addressee": pending["from"], "topic": scene["topic"]}
    if "invite" in view["acts"] and "dice_together" in view["invitations"]:
        other = next(item for item in scene["participants"] if item["id"] != me["id"])
        return {"line": "A game of dice?", "act": "invite", "addressee": other["id"], "topic": scene["topic"],
                "invitation": "dice_together"}
    return dict(scripted_turn(view))


@pytest.mark.parametrize("seed", [pytest.param(1, id="seed-1"), pytest.param(2, id="seed-2")])
def test_a_game_invited_to_in_the_first_evening_reaches_a_result(seed: int) -> None:
    room = json.loads((ROOT / "data" / "tavern.json").read_text())
    cards = parse_cards([json.loads(path.read_text()) for path in sorted((ROOT / "data" / "characters").glob("*.json"))])
    scenario = parse_scenario(json.loads((ROOT / "data" / "scenarios" / "first_evening.json").read_text()), cards)
    world = open_evening(room, scenario, seed)
    config = {"model": "jev-latest", "timeout": 1.0, "temperature": 0.25, "typesafe_api_key": None}
    evening = asyncio.run(run_evening(world, config, Random(seed), Evaluators(never_asked, never_asked),
                                      Pace(step=0.25, model_latency=1.0, time_limit=1200.0), dicing_writer))
    won = [event["message"] for event in evening.events if event["type"] == "dice_won"]
    started = [event for event in evening.events if event["type"] == "dice_started"]
    assert started and won, "no game of dice was played"
    counts = dice_metrics(evening.events)
    assert (counts["games"], sum(counts["wins"].values())) == (len(won), len(won))
