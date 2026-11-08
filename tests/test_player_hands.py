"""The player's hands: `act` starts an action for the played guest, `options` lists what is open to them."""

from collections.abc import Callable
from typing import Any

import pytest

from tavern.body.activities import ACTIVITIES
from tavern.evening.player_commands import act, options
from tavern.hall.world import create_world
from test_decisions import room

TAKE_BEER = {"id": "take_beer:tap", "verb": "take_beer", "target_id": "tap"}


def played(steering: bool = True) -> dict[str, Any]:
    """Ada, who stands next to the tap with Bea beside her, is the played guest."""
    world = create_world(room())
    ada(world).update(x=5, y=1)
    next(item for item in world["actors"] if item["id"] == "bea").update(x=4, y=1)
    world["player"] = {"actor_id": "ada", "steering": steering}
    return world


def ada(world: dict[str, Any]) -> dict[str, Any]:
    """Find Ada in the hall."""
    return next(item for item in world["actors"] if item["id"] == "ada")


def no_player(world: dict[str, Any]) -> None:
    """Nobody plays at this evening."""
    world["player"] = None


def on_autopilot(world: dict[str, Any]) -> None:
    """The player has given the wheel back."""
    world["player"]["steering"] = False


def not_yet_arrived(world: dict[str, Any]) -> None:
    """Ada is still expected at the door."""
    world["expected"].append(world["actors"].pop(0))


def test_an_accepted_act_starts_the_action_and_says_the_player_chose_it() -> None:
    world = played()
    act(world, {"type": "act", "action": TAKE_BEER})
    assert (ada(world)["action"]["verb"], ada(world)["decision"]) == (
        "take_beer", {"source": "player", "scores": {}, "error": None})


def test_an_accepted_act_logs_one_player_act_event_with_the_verb() -> None:
    world = played()
    act(world, {"type": "act", "action": TAKE_BEER})
    events = [item for item in world["events"] if item["type"] == "player_act"]
    assert [(item["actor_id"], item["verb"]) for item in events] == [("ada", "take_beer")]


@pytest.mark.parametrize("prepare, command, reason", [
    pytest.param(no_player, {"action": TAKE_BEER}, "needs a player", id="no-player"),
    pytest.param(on_autopilot, {"action": TAKE_BEER}, "autopilot", id="on-autopilot"),
    pytest.param(not_yet_arrived, {"action": TAKE_BEER}, "not in the hall", id="not-yet-arrived"),
    pytest.param(None, {"action": {**TAKE_BEER, "target_id": "nowhere"}}, "Target no longer exists",
                 id="the-world-refuses"),
    pytest.param(None, {"action": {**TAKE_BEER, "verb": "juggle"}}, "Unknown action verb", id="unknown-verb"),
    pytest.param(None, {}, "needs an action", id="no-action"),
    pytest.param(None, {"action": "take_beer"}, "needs an action", id="action-is-not-a-record"),
])
def test_an_act_that_cannot_start_is_refused_and_changes_nothing(
        prepare: Callable[[dict[str, Any]], None] | None, command: dict[str, Any], reason: str) -> None:
    world = played()
    if prepare:
        prepare(world)
    events = len(world["events"])
    with pytest.raises(ValueError, match=reason):
        act(world, {"type": "act", **command})
    assert [item for item in world["events"][events:] if item["type"] == "player_act"] == []


def verbs(reply: dict[str, Any]) -> list[str]:
    """List the verbs of an options reply."""
    return [item["action"]["verb"] for item in reply["options"]]


def thirsty(world: dict[str, Any]) -> None:
    """Ada is thirsty and keen on company, so the tap and Bea are both worth her while."""
    ada(world)["needs"].update(thirst=90.0, social=90.0)


@pytest.mark.parametrize("command, expected", [
    pytest.param({}, ("options", None, True), id="everything-open"),
    pytest.param({"target_id": "tap"}, ("options", "tap", True), id="aimed-at-the-tap"),
    pytest.param({"target_id": "nobody"}, ("options", "nobody", False), id="aimed-at-something-that-is-not-there"),
])
def test_options_lists_the_legal_actions_of_the_played_guest(command: dict[str, Any],
                                                             expected: tuple[str, str | None, bool]) -> None:
    world = played()
    thirsty(world)
    reply = options(world, {"type": "options", **command})
    assert (reply["type"], reply["target_id"], "take_beer" in verbs(reply)) == expected


def test_options_aimed_at_a_guest_hold_only_verbs_aimed_at_them() -> None:
    world = played()
    thirsty(world)
    reply = options(world, {"type": "options", "target_id": "bea"})
    assert (len(reply["options"]) > 0, {item["action"]["target_id"] for item in reply["options"]}) == (True, {"bea"})


def test_an_option_carries_the_action_the_world_would_start_and_the_verbs_label() -> None:
    world = played()
    thirsty(world)
    reply = options(world, {"type": "options", "target_id": "tap"})
    assert reply["options"] == [{"action": TAKE_BEER, "label": ACTIVITIES["take_beer"].label}]
    act(world, {"type": "act", "action": reply["options"][0]["action"]})
    assert ada(world)["action"]["verb"] == "take_beer"


def test_options_leave_the_world_as_it_is_apart_from_what_the_guest_knows() -> None:
    world = played()
    thirsty(world)
    before = {key: world[key] for key in ("events", "time", "tick")} | {"action": ada(world)["action"]}
    options(world, {"type": "options"})
    assert {key: world[key] for key in ("events", "time", "tick")} | {"action": ada(world)["action"]} == before


@pytest.mark.parametrize("prepare, reason", [
    pytest.param(no_player, "needs a player", id="no-player"),
    pytest.param(on_autopilot, "autopilot", id="on-autopilot"),
    pytest.param(not_yet_arrived, "not in the hall", id="not-yet-arrived"),
])
def test_options_need_a_played_guest_in_the_hall(prepare: Callable[[dict[str, Any]], None], reason: str) -> None:
    world = played()
    prepare(world)
    with pytest.raises(ValueError, match=reason):
        options(world, {"type": "options"})


@pytest.mark.parametrize("target", [pytest.param(7, id="a-number"), pytest.param("", id="empty")])
def test_options_refuse_a_target_that_is_not_an_id(target: Any) -> None:
    with pytest.raises(ValueError, match="target_id"):
        options(played(), {"type": "options", "target_id": target})
