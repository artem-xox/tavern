"""Overhearing: every spoken line makes a sound, and guests nearby catch the act and the gist."""

from collections.abc import Callable
from typing import Any

import pytest

from tavern.social.overhearing import TURN_SOUNDS, overhear_turn
from social_hall import actor, advance, say, scene_of, seated_talk


def dislikes(world: dict[str, Any]) -> None:
    """Ada dislikes Bea, so she may insult her."""
    actor(world, "ada")["relations"]["bea"] = {"name": "Bea", "opinion": -40.0, "familiarity": "acquaintance"}


def cid_thinks(world: dict[str, Any], opinion: float, familiarity: str) -> None:
    """Give Cid a relation to Bea."""
    actor(world, "cid")["relations"]["bea"] = {"name": "Bea", "opinion": opinion, "familiarity": familiarity}


def friend(world: dict[str, Any]) -> None:
    """Cid is Bea's old friend."""
    cid_thinks(world, 50.0, "friend")


def admirer(world: dict[str, Any]) -> None:
    """Cid met Bea tonight and thinks highly of her."""
    cid_thinks(world, 40.0, "acquaintance")


def cool(world: dict[str, Any]) -> None:
    """Cid barely likes Bea."""
    cid_thinks(world, 5.0, "acquaintance")


def stranger(world: dict[str, Any]) -> None:
    """Cid does not know Bea."""


def far_away(world: dict[str, Any]) -> None:
    """Cid, Bea's friend, has walked to the far end of the hall by the door."""
    friend(world)
    cid = actor(world, "cid")
    cid.update(x=11, y=7, seat_id=None, action=None, status="idle")
    cid["traits"]["curiosity"] = 0.0


def insulted(world: dict[str, Any]) -> list[tuple[str, str | None]]:
    """Cid's thoughts after Ada insults Bea at the next table."""
    dislikes(world)
    say(world, "insult", "You're a cheat, Bea.")
    return [(item["kind"], item["about"]) for item in actor(world, "cid")["thoughts"]]


@pytest.mark.parametrize("relation, wall, thoughts", [
    pytest.param(friend, False, [("friend_insulted", "ada")], id="friend-overhears-at-the-next-table"),
    pytest.param(admirer, False, [("friend_insulted", "ada")], id="high-opinion-is-enough"),
    pytest.param(cool, False, [], id="lukewarm-listener-shrugs"),
    pytest.param(stranger, False, [], id="stranger-shrugs"),
    pytest.param(friend, True, [], id="wall-muffles-it"),
    pytest.param(far_away, False, [], id="out-of-earshot"),
])
def test_an_insult_to_someone_liked_is_resented_by_who_overhears_it(
        relation: Callable[[dict[str, Any]], None], wall: bool, thoughts: list[tuple[str, str | None]]) -> None:
    world = seated_talk(wall=wall)
    advance(world, 0.2)
    relation(world)
    assert insulted(world) == thoughts


def test_overheard_insult_is_remembered_in_the_listeners_words() -> None:
    world = seated_talk()
    friend(world)
    insulted(world)
    memory = [item["message"] for item in actor(world, "cid")["memory"] if item["type"] == "overheard"]
    assert memory == ["Cid overheard Ada insult Bea: \"You're a cheat, Bea.\""]


def test_a_member_of_the_scene_takes_offence_too() -> None:
    world = seated_talk(cid_joins=True)
    friend(world)
    dislikes(world)
    say(world, "insult", "You're a cheat.", addressee="bea")
    assert [(item["kind"], item["about"]) for item in actor(world, "cid")["thoughts"]] == [("friend_insulted", "ada")]


@pytest.mark.parametrize("act, kind", [
    pytest.param("small_talk", "chat", id="talk-is-chat"),
    pytest.param("joke", "laughter", id="joke-draws-laughter"),
    pytest.param("insult", "insult", id="insult-rings-out"),
])
def test_each_spoken_line_makes_a_sound_from_the_whole_company(act: str, kind: str) -> None:
    world = seated_talk()
    advance(world, 0.2)
    world["stimuli"].clear()
    turn = {"speaker": "ada", "addressee": "bea", "line": "Well now.", "act": act, "time": world["time"]}
    sound = overhear_turn(world, scene_of(world), turn)
    assert (world["stimuli"], sound["kind"], sorted(sound["sources"]), sound["about"]) == (
        [sound], kind, ["ada", "bea"], ["bea"])


def test_insults_are_louder_than_talk_and_laughter() -> None:
    chat, laughter, insult = (TURN_SOUNDS[kind] for kind in ("small_talk", "joke", "insult"))
    assert chat.loudness <= laughter.loudness < insult.loudness and insult.reach > chat.reach
