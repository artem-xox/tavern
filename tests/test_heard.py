"""What a guest remembers of tonight's talk: the lines they spoke and heard, kept per guest and saved."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.persistence import load_world, save_world
from tavern.hall.world import start_action
from tavern.mind.haiku_turns import turn_question
from tavern.mind.intentions import intention_question, intention_view
from tavern.social.turns import turn_view
from social_hall import LOOKS, actor, advance, command, say, scene_of, seated_talk


def late_joiner_world() -> tuple[dict[str, Any], float]:
    """Ada and Bea speak two lines; then Cid sits down and joins. Also returns when he joined."""
    world = seated_talk(social=100.0)
    say(world, "small_talk", "Cold out.")
    say(world, "joke", "Colder in here.")
    assert start_action(world, "cid", command("sit", "n"))["accepted"]
    advance(world, 3)
    assert start_action(world, "cid", command("join_conversation", "ada"))["accepted"]
    while "cid" not in scene_of(world)["participants"]:
        advance(world, 0.1)
    return world, world["time"]


def lines_of(world: dict[str, Any], actor_id: str) -> list[str]:
    """The words a guest remembers, oldest first."""
    return [item["line"] for item in actor(world, actor_id)["heard"]]


@pytest.mark.parametrize("actor_id, lines", [
    pytest.param("ada", ["Cold out."], id="speaker-hears-themselves"),
    pytest.param("bea", ["Cold out."], id="listener"),
    pytest.param("cid", [], id="outsider-at-the-far-table"),
])
def test_a_spoken_line_reaches_every_member_and_no_outsider(actor_id: str, lines: list[str]) -> None:
    world = seated_talk(social=100.0)
    say(world, "small_talk", "Cold out.")
    assert lines_of(world, actor_id) == lines


def test_a_heard_line_records_who_said_it_when_and_how() -> None:
    world = seated_talk(social=100.0)
    say(world, "small_talk", "Cold out.")
    [turn] = scene_of(world)["turns"]
    assert actor(world, "bea")["heard"] == [{"time": turn["time"], "scene_id": scene_of(world)["id"],
                                             "speaker_id": "ada", "speaker": "Ada", "line": "Cold out.",
                                             "act": "small_talk"}]


@pytest.mark.parametrize("listener, expected", [
    pytest.param("ada", "Ada", id="oneself-by-name"),
    pytest.param("bea", LOOKS["ada"], id="stranger-by-looks"),
])
def test_the_speaker_is_recorded_as_the_listener_called_them(listener: str, expected: str) -> None:
    world = seated_talk(cards=True, social=100.0)
    say(world, "small_talk", "Cold out.")
    assert actor(world, listener)["heard"][0]["speaker"] == expected


def test_a_guest_who_joins_later_lacks_the_earlier_lines() -> None:
    world, joined_at = late_joiner_world()
    say(world, "small_talk", "Bring a coat.")
    ada = [item["line"] for item in actor(world, "ada")["heard"]]
    before = [item["line"] for item in actor(world, "ada")["heard"] if item["time"] < joined_at]
    assert ["Cold out.", "Colder in here."] == before[:2] and "Bring a coat." in ada
    assert lines_of(world, "cid") == ada[len(before):]
    assert "Bring a coat." in lines_of(world, "cid")


@pytest.mark.parametrize("recall, expected", [
    pytest.param(1, ["Line 3"], id="keeps-only-the-newest"),
    pytest.param(2, ["Line 2", "Line 3"], id="two-newest"),
    pytest.param(40, ["Line 1", "Line 2", "Line 3"], id="cap-above-the-count-keeps-all"),
])
def test_the_cap_keeps_the_newest_lines(recall: int, expected: list[str]) -> None:
    world = seated_talk(social=100.0)
    world["rules"]["conversation"]["recall_lines"] = recall
    for number in (1, 2, 3):
        say(world, "small_talk", f"Line {number}")
    assert lines_of(world, "bea") == expected


def test_heard_lines_survive_save_and_load(tmp_path: Path) -> None:
    world, _ = late_joiner_world()
    save_world(world, tmp_path / "evening.json")
    assert load_world(tmp_path / "evening.json") == world


def corrupt_line(world: dict[str, Any]) -> None:
    """Break the first remembered line of Ada's."""
    actor(world, "ada")["heard"][0]["act"] = "shout"


@pytest.mark.parametrize("corrupt", [
    pytest.param(lambda world: world.update(schema_version=5), id="version-5-save-without-heard"),
    pytest.param(lambda world: actor(world, "ada").pop("heard"), id="missing-heard"),
    pytest.param(lambda world: actor(world, "ada").update(heard="Cold out."), id="heard-is-not-a-list"),
    pytest.param(lambda world: actor(world, "ada")["heard"].append("Cold out."), id="line-is-not-a-record"),
    pytest.param(lambda world: actor(world, "ada")["heard"][0].pop("line"), id="line-without-words"),
    pytest.param(lambda world: actor(world, "ada")["heard"][0].update(line=""), id="empty-line"),
    pytest.param(lambda world: actor(world, "ada")["heard"][0].update(time=-1), id="negative-time"),
    pytest.param(corrupt_line, id="unknown-act"),
    pytest.param(lambda world: actor(world, "ada")["heard"][0].update(extra=1), id="unknown-field"),
    pytest.param(lambda world: world["rules"]["conversation"].update(recall_lines=1), id="more-than-the-cap"),
])
def test_corrupt_heard_lines_are_rejected(tmp_path: Path, corrupt: Callable[[dict[str, Any]], Any]) -> None:
    world, _ = late_joiner_world()
    corrupt(world)
    save_world(world, tmp_path / "corrupt.json")
    with pytest.raises(ValueError):
        load_world(tmp_path / "corrupt.json")


def said(scene_id: str, speaker_id: str, line: str, time: float = 1.0) -> dict[str, Any]:
    """Build a remembered line, as its listener called the speaker."""
    return {"time": time, "scene_id": scene_id, "speaker_id": speaker_id, "speaker": speaker_id.title(),
            "line": line, "act": "small_talk"}


def remembering(*lines: dict[str, Any]) -> dict[str, Any]:
    """Ada and Bea are talking in a scene; Ada remembers the given lines."""
    world = seated_talk(social=100.0)
    actor(world, "ada")["heard"] = list(lines)
    return world


def earlier_of(world: dict[str, Any]) -> list[dict[str, Any]]:
    """What the turn writer is shown of Ada's earlier talk."""
    return turn_view(world, scene_of(world))["speaker"]["earlier"]


OLD_TALK = [said("old-1", "bea", "Snow on the pass."), said("old-1", "ada", "So I heard.")]
OTHER_TALK = [said("old-2", "cid", "Salt is dear."), said("old-2", "cid", "Dearer every year."),
              said("old-2", "dan", "Hush."), said("old-2", "cid", "Aye.")]


@pytest.mark.parametrize("lines, expected", [
    pytest.param([], [], id="nothing-heard"),
    pytest.param(OLD_TALK, [{"scene_id": "old-1", "with": ["Bea"], "lines": [
        {"speaker": "Bea", "line": "Snow on the pass."}, {"speaker": "Ada", "line": "So I heard."}]}],
                 id="one-earlier-scene-without-oneself-among-the-voices"),
    pytest.param([said("old-1", "ada", "Anyone there?")], [{"scene_id": "old-1", "with": [], "lines": [
        {"speaker": "Ada", "line": "Anyone there?"}]}], id="only-their-own-line"),
    pytest.param([*OLD_TALK, *OTHER_TALK[:3]], [
        {"scene_id": "old-1", "with": ["Bea"], "lines": [{"speaker": "Bea", "line": "Snow on the pass."},
                                                          {"speaker": "Ada", "line": "So I heard."}]},
        {"scene_id": "old-2", "with": ["Cid", "Dan"], "lines": [{"speaker": "Cid", "line": "Salt is dear."},
                                                                 {"speaker": "Cid", "line": "Dearer every year."},
                                                                 {"speaker": "Dan", "line": "Hush."}]}],
                 id="scenes-oldest-first-voices-listed-once"),
    pytest.param([said("conversation-0", "bea", "Evening.")], [], id="the-current-scene-is-left-out"),
])
def test_the_turn_view_groups_earlier_lines_by_scene_and_leaves_out_the_current_one(
        lines: list[dict[str, Any]], expected: list[dict[str, Any]]) -> None:
    assert earlier_of(remembering(*lines)) == expected


def test_the_turn_view_caps_earlier_lines_at_the_newest_24() -> None:
    lines = [said("old-1", "bea", f"Line {number}") for number in range(1, 31)]
    shown = [item["line"] for scene in earlier_of(remembering(*lines)) for item in scene["lines"]]
    assert shown == [f"Line {number}" for number in range(7, 31)]


def test_the_intention_view_holds_the_latest_8_lines_current_scene_included() -> None:
    world = remembering(*[said("conversation-0", "bea", f"Line {number}") for number in range(1, 13)])
    view = intention_view(world, actor(world, "ada"), {"kind": "scene_ended", "text": "Talk ended", "time": 0.0})
    assert [item["line"] for scene in view["earlier"] for item in scene["lines"]] == [
        f"Line {number}" for number in range(5, 13)]


@pytest.mark.parametrize("lines, present, absent", [
    pytest.param(OLD_TALK, ["EARLIER TONIGHT", "With Bea", 'Bea: "Snow on the pass."', 'Ada: "So I heard."'], [],
                 id="lines-by-scene"),
    pytest.param([], [], ["EARLIER TONIGHT"], id="nothing-heard-no-heading"),
])
def test_the_question_content_holds_the_earlier_lines(lines: list[dict[str, Any]], present: list[str],
                                                      absent: list[str]) -> None:
    world = remembering(*lines)
    content = turn_question(turn_view(world, scene_of(world)))["content"]
    assert [text in content for text in present + absent] == [True] * len(present) + [False] * len(absent)


@pytest.mark.parametrize("lines, expected", [
    pytest.param(OLD_TALK, True, id="lines-shown"),
    pytest.param([], False, id="nothing-heard-nothing-shown"),
])
def test_the_intention_question_holds_the_lines_they_heard(lines: list[dict[str, Any]], expected: bool) -> None:
    world = remembering(*lines)
    view = intention_view(world, actor(world, "ada"), {"kind": "scene_ended", "text": "Talk ended", "time": 0.0})
    content = intention_question("Shared rules.", view)["content"]
    assert ('Bea: "Snow on the pass."' in content) is expected
