"""The Haiku turn writer: its cached question, its answer schema, and the boundary that rejects bad lines."""

import asyncio
from itertools import count
from typing import Any

import pytest

from tavern.adapters.claude import ClaudeError
from tavern.social.conversation import ACTS
from tavern.mind.haiku_turns import RejectedTurn, claude_writer, parse_turn, turn_question, writer_mode
from tavern.mind.questions import Question
from tavern.evening.recording import Record, record_questions, replay_questions
from tavern.social.scenes import conversation_of
from tavern.mind.scripted import scripted_turn
from tavern.social.thoughts import think
from tavern.social.turns import claim_turns, deliver_turn, turn_view
from tavern.hall.world import create_world, start_action

ADA = {"id": "ada", "sprite": "visitor", "name": "Ada", "occupation": "salt trader",
       "background": "Ada drives salt over the pass.", "temperament": "Warm but shrewd.",
       "speech": "Quick, full of prices.", "quirks": "Counts coins aloud.", "secret": "She owes the miller.",
       "goal": "Sell her last sack of salt.", "params": {}}
BEA = {**ADA, "id": "bea", "name": "Bea", "occupation": "pilgrim", "goal": "Find a guide over the pass."}
GOOD = {"line": "Salt's dear this year, Bea.", "act": "small_talk", "addressee": "bea", "topic": "salt prices"}


def chair(chair_id: str, x: int, y: int) -> dict[str, Any]:
    """Build a walkable chair at the table."""
    return {"id": chair_id, "kind": "chair", "name": f"Table · {chair_id}", "x": x, "y": y, "walkable": True,
            "table_id": "table", "interaction_spots": [[x, y]]}


def scene_world(knows_tap: bool = False) -> dict[str, Any]:
    """Ada (salt trader) and Bea (pilgrim) seated at one table; Ada has just started talking to Bea."""
    world = create_world({"width": 10, "height": 5, "blocked": [], "objects": [
        {"id": "table", "kind": "table", "name": "Table", "x": 3, "y": 2, "width": 2, "height": 1},
        chair("west", 2, 2), chair("east", 5, 2),
        {"id": "tap", "kind": "tap", "name": "Tap", "x": 9, "y": 0, "interaction_spots": [[8, 0]], "stock": 9}],
        "actors": [{"id": "ada", "name": "Ada", "x": 2, "y": 2, "card": ADA},
                   {"id": "bea", "name": "Bea", "x": 5, "y": 2, "card": BEA}]}, 3)
    for actor_id, seat in (("ada", "west"), ("bea", "east")):
        assert start_action(world, actor_id, {"id": f"sit:{seat}", "verb": "sit", "target_id": seat})["accepted"]
        people(world)[actor_id]["needs"]["social"] = 90.0
    if knows_tap:
        people(world)["ada"]["knowledge"]["objects"]["tap"] = {**world["map"]["objects"][3], "last_seen": 0.0}
    assert start_action(world, "ada", {"id": "talk:bea", "verb": "talk", "target_id": "bea"})["accepted"]
    return world


def people(world: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Guests by ID."""
    return {item["id"]: item for item in world["actors"]}


def view_of(world: dict[str, Any]) -> dict[str, Any]:
    """The view of Ada and Bea's scene's next turn."""
    return turn_view(world, conversation_of(world, "ada"))


def bea_speaks(world: dict[str, Any]) -> dict[str, Any]:
    """Let Ada greet, so Bea writes the second line; return Bea's view."""
    scene = conversation_of(world, "ada")
    scene["turns"].append({"speaker": "ada", "addressee": "bea", "line": "Evening, Bea!", "act": "greet",
                           "time": 1.0})
    return view_of(world)


def test_shared_prefix_is_the_same_for_every_speaker_and_scene() -> None:
    world = scene_world()
    first, second = turn_question(view_of(world)), turn_question(bea_speaks(world))
    assert first["system"][0] == second["system"][0]
    assert (first["system"][1] != second["system"][1], first["content"] != second["content"]) == (True, True)


def test_shared_prefix_is_long_enough_to_cache() -> None:
    # Haiku 4.5 caches prefixes of at least 4096 tokens. The token counting API put this prefix
    # at 4,857 tokens for 17,567 characters (3.6 per token), so 16,500 characters keep a margin
    # over 4096 tokens. Live usage confirms the cache reads.
    assert len(turn_question(view_of(scene_world()))["system"][0]) >= 16_500


@pytest.mark.parametrize("offered", [
    pytest.param({}, id="nothing-offered"),
    pytest.param({"greet": ACTS["greet"].meaning}, id="single-act-offered"),
    pytest.param({name: act.meaning for name, act in ACTS.items()}, id="every-act-offered"),
])
def test_acts_and_their_meanings_come_from_the_table(offered: dict[str, str]) -> None:
    # The cached prefix and the schema cover the whole table whatever the moment offers, so
    # they never change between turns; the offer itself is in the per-call content.
    question = turn_question({**view_of(scene_world()), "acts": offered})
    assert all(f"{name}: {act.meaning}" in question["system"][0] for name, act in ACTS.items())
    assert question["schema"]["properties"]["act"]["enum"] == list(ACTS)


def test_answer_schema_asks_for_exactly_a_line_act_addressee_topic_invitation_and_fact() -> None:
    schema = turn_question(view_of(scene_world()))["schema"]
    assert (schema["type"], sorted(schema["required"]), schema["additionalProperties"]) == (
        "object", ["act", "addressee", "fact_id", "invitation", "line", "topic"], False)
    assert schema["properties"]["addressee"] == {"anyOf": [{"type": "string"}, {"type": "null"}],
                                                 "description": schema["properties"]["addressee"]["description"]}


def test_card_goes_in_the_second_cached_block() -> None:
    card = turn_question(view_of(scene_world()))["system"][1]
    assert all(ADA[key] in card for key in ("occupation", "background", "temperament", "speech", "quirks", "secret"))


@pytest.mark.parametrize("prepare, expected", [
    pytest.param(lambda world: None, ["No one has spoken yet", "Bea (id \"bea\")", "You are sober.",
                                      "Sell her last sack of salt.", "Places you know: none"], id="opening-line"),
    pytest.param(lambda world: people(world)["ada"].update(drunkenness=0.5), ["They are drunk"], id="drunk-speech"),
    pytest.param(lambda world: think(people(world)["ada"], "quarrel", 0.0, "Quarreled with Bea about salt",
                                     "quarrel", about=people(world)["bea"]),
                 ["Quarreled with Bea about salt", "dislike Bea"], id="thoughts-about-those-present"),
    pytest.param(lambda world: people(world)["ada"]["knowledge"]["objects"].update(
        tap={"id": "tap", "kind": "tap", "name": "Tap"}), ["Places you know: Tap (tap)"], id="known-places"),
])
def test_per_call_content_holds_the_scene_mood_drink_places_and_goal(prepare: Any, expected: list[str]) -> None:
    world = scene_world()
    prepare(world)
    content = turn_question(view_of(world))["content"]
    assert [text for text in expected if text not in content] == []


NUDGES = ("Pressing now", "had enough company", "not yet told")


@pytest.mark.parametrize("needs, knows_tap, nudges", [
    pytest.param({}, False, [], id="calm-and-placeless-no-nudge"),
    pytest.param({"bladder": 85.0}, False, ["Pressing now"], id="pressing-need"),
    pytest.param({"bladder": 85.0, "thirst": 90.0, "social": 10.0}, True, list(NUDGES), id="everything-at-once"),
    pytest.param({"social": 10.0}, False, ["had enough company"], id="enough-company"),
    pytest.param({}, True, ["not yet told"], id="place-not-yet-shared"),
])
def test_content_nudges_toward_the_acts_the_moment_calls_for(needs: dict[str, float], knows_tap: bool,
                                                             nudges: list[str]) -> None:
    world = scene_world(knows_tap)
    people(world)["ada"]["needs"].update(needs)
    content = turn_question(view_of(world))["content"]
    assert [text for text in NUDGES if text in content] == nudges


def test_place_shared_once_is_not_nudged_again() -> None:
    world = scene_world(knows_tap=True)
    conversation_of(world, "ada")["turns"] += [
        {"speaker": "ada", "addressee": "bea", "line": "Tap's by the bar.", "act": "share_place", "time": 1.0},
        {"speaker": "bea", "addressee": "ada", "line": "Thanks.", "act": "small_talk", "time": 3.0}]
    assert "not yet told" not in turn_question(view_of(world))["content"]


def test_recent_lines_are_in_the_content() -> None:
    assert 'Ada to Bea [greet]: "Evening, Bea!"' in turn_question(bea_speaks(scene_world()))["content"]


@pytest.mark.parametrize("answer", [
    pytest.param(GOOD, id="addressed"),
    pytest.param({**GOOD, "addressee": None}, id="to-everyone"),
    pytest.param({**GOOD, "line": "x" * 160}, id="longest-line"),
])
def test_valid_answers_pass(answer: dict[str, Any]) -> None:
    assert parse_turn(view_of(scene_world()), answer) == answer


def test_known_place_may_be_shared() -> None:
    answer = {**GOOD, "act": "share_place", "line": "Ale's at the tap by the wall."}
    assert parse_turn(view_of(scene_world(knows_tap=True)), answer) == answer


@pytest.mark.parametrize("answer", [
    pytest.param("Salt's dear.", id="not-an-object"),
    pytest.param({}, id="empty-object"),
    pytest.param({key: GOOD[key] for key in ("line", "act", "addressee")}, id="missing-topic"),
    pytest.param({**GOOD, "mood": "glad"}, id="unknown-field"),
    pytest.param({**GOOD, "act": "insult"}, id="unknown-act"),
    pytest.param({**GOOD, "addressee": "ada"}, id="talks-to-herself"),
    pytest.param({**GOOD, "addressee": "zed"}, id="addressee-not-present"),
    pytest.param({**GOOD, "addressee": 7}, id="malformed-addressee"),
    pytest.param({**GOOD, "line": "  "}, id="blank-line"),
    pytest.param({**GOOD, "line": "x" * 161}, id="line-too-long"),
    pytest.param({**GOOD, "line": "Salt.\nSalt!"}, id="two-lines"),
    pytest.param({**GOOD, "line": "*sighs* Salt's dear."}, id="stage-direction"),
    pytest.param({**GOOD, "line": "(sighing) Salt's dear."}, id="parenthetical-direction"),
    pytest.param({**GOOD, "topic": "x" * 61}, id="topic-too-long"),
    pytest.param({**GOOD, "act": "share_place", "line": "Ale's at the tap."}, id="shares-a-place-she-does-not-know"),
])
def test_invalid_answers_are_rejected(answer: Any) -> None:
    with pytest.raises(RejectedTurn):
        parse_turn(view_of(scene_world()), answer)


def asking(*answers: Any) -> Any:
    """A fake Claude port answering in turn, noting the questions it was asked."""
    replies, asked = iter(answers), []

    async def ask(question: Question) -> Any:
        asked.append(question)
        return next(replies)
    ask.asked = asked  # type: ignore[attr-defined]
    return ask


def test_writer_asks_once_and_returns_the_checked_line() -> None:
    world = scene_world()
    ask = asking(GOOD)
    assert asyncio.run(claude_writer(ask)(view_of(world), {})) == GOOD
    assert ask.asked == [turn_question(view_of(world))]


def test_invalid_answer_falls_back_to_a_scripted_line() -> None:
    world = scene_world()
    [(scene_id, turn, view)] = claim_turns(world)
    task = asyncio.run(_settle(claude_writer(asking({**GOOD, "act": "insult"}))(view, {})))
    deliver_turn(world, scene_id, turn, task.result)
    assert conversation_of(world, "ada")["written"] == scripted_turn(view_of(world))
    assert world["events"][-1]["type"] == "turn_failed" and "insult" in world["events"][-1]["message"]


async def _settle(job: Any) -> "asyncio.Task[Any]":
    task = asyncio.ensure_future(job)
    await asyncio.wait([task])
    return task


def metered(*answers: dict[str, Any]) -> Any:
    """A fake metered Claude answering in turn, with cache reads in its usage."""
    replies = iter(answers)

    async def ask(question: Question) -> Any:
        return next(replies), {"input_tokens": 300, "output_tokens": 30, "cache_read_input_tokens": 4500,
                               "cache_creation_input_tokens": 0}
    return ask


@pytest.mark.parametrize("answers", [
    pytest.param([], id="empty-no-turns"),
    pytest.param([GOOD], id="single-turn"),
    pytest.param([GOOD, GOOD], id="duplicate-turns"),
])
def test_recorded_turns_replay_identically(answers: list[dict[str, Any]]) -> None:
    world, records = scene_world(), []
    ticks = count(0.0, 0.5)
    live = claude_writer(record_questions("turn", metered(*answers), records.append, lambda: next(ticks),
                                          ClaudeError))
    lines = [asyncio.run(live(view_of(world), {})) for _ in answers]
    replayed = claude_writer(replay_questions("turn", records, ClaudeError))
    assert [asyncio.run(replayed(view_of(world), {})) for _ in answers] == lines
    assert [record["kind"] for record in records] == ["turn"] * len(answers)


def test_recorded_failure_replays_as_a_failure() -> None:
    world, records = scene_world(), []

    async def refusing(question: Question) -> Any:
        raise ClaudeError("Claude stopped early: refusal")
    live = claude_writer(record_questions("turn", refusing, records.append, lambda: 0.0, ClaudeError))
    with pytest.raises(ClaudeError):
        asyncio.run(live(view_of(world), {}))
    with pytest.raises(ClaudeError):
        asyncio.run(claude_writer(replay_questions("turn", records, ClaudeError))(view_of(world), {}))


def test_unrecorded_turn_fails_loudly_in_a_replay() -> None:
    no_records: list[Record] = []
    with pytest.raises(LookupError):
        asyncio.run(claude_writer(replay_questions("turn", no_records, ClaudeError))(view_of(scene_world()), {}))


@pytest.mark.parametrize("requested, keyed, expected", [
    pytest.param(None, True, "haiku", id="default-with-a-key"),
    pytest.param(None, False, "scripted", id="default-without-a-key"),
    pytest.param("scripted", True, "scripted", id="scripted-asked-despite-a-key"),
    pytest.param("haiku", True, "haiku", id="haiku-asked-with-a-key"),
])
def test_writer_mode_uses_haiku_when_a_key_is_configured(requested: str | None, keyed: bool, expected: str) -> None:
    mode, note = writer_mode(requested, keyed)
    assert (mode, note is None) == (expected, requested is not None or keyed)


@pytest.mark.parametrize("requested", [
    pytest.param("haiku", id="haiku-without-a-key"),
    pytest.param("", id="empty-name"),
    pytest.param("opus", id="unknown-writer"),
])
def test_impossible_writer_mode_fails_loudly(requested: str) -> None:
    with pytest.raises(ValueError):
        writer_mode(requested, False)


INTENT = {"thought": "Bea looks like she knows the pass.", "intention": "Ask Bea which guide to hire.",
          "written_at": 5.0, "trigger": {"kind": "arrival", "text": "Ada has just come in", "time": 5.0}}


@pytest.mark.parametrize("intention, expected, absent", [
    pytest.param(None, [], ["What you mean to do"], id="no-intention-yet"),
    pytest.param(INTENT, ["What you mean to do: Ask Bea which guide to hire."], [], id="intention-written"),
])
def test_the_speakers_current_intention_is_in_the_moment(intention: Any, expected: list[str],
                                                         absent: list[str]) -> None:
    world = scene_world()
    people(world)["ada"]["intention"] = intention
    content = turn_question(view_of(world))["content"]
    assert ([text for text in expected if text not in content], [text for text in absent if text in content]) == ([], [])
