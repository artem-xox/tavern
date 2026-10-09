"""A healer who sees someone unwell: what the minds are told of them, how the local policy weighs a remedy, and the metrics."""

from typing import Any

import pytest

from tavern.evening.ailment_metrics import ailment_counts
from tavern.mind.briefing import brief
from tavern.mind.haiku_turns import turn_question
from tavern.mind.local_policy import local_scores
from tavern.mind.options import option_text
from tavern.social.scenes import conversation_of
from tavern.social.turns import turn_view
from hostile_view import person, view
from social_hall import actor, command, seated_talk


def sees(observation: dict[str, Any], *people: dict[str, Any]) -> dict[str, Any]:
    """Ada's observation with these people in sight."""
    observation["people"] = list(people)
    return observation


def pale(person_id: str, **fields: Any) -> dict[str, Any]:
    """Someone who looks unwell."""
    return person(person_id, ailing=True, **fields)


def healer(*people: dict[str, Any], remedies: int = 3, **fields: Any) -> dict[str, Any]:
    """Ada's observation, carrying remedies, with these people in sight."""
    observation = view(None, list(people), **fields)
    observation["actor"]["inventory"] = {"beer": 0, "remedy": remedies, "keepsake": 0}
    return observation


@pytest.mark.parametrize("someone, said", [
    pytest.param(pale("bea"), True, id="an-unwell-guest-looks-it"),
    pytest.param(person("bea", ailing=False), False, id="a-well-guest-does-not"),
])
def test_the_briefing_says_who_looks_unwell(someone: dict[str, Any], said: bool) -> None:
    text = brief(sees(view(), someone), [])["situation"]
    assert ("Bea sits across the table from them, looking pale and feverish" in text) is said


def test_a_standing_guest_who_is_unwell_looks_it_too() -> None:
    text = brief(sees(view(), pale("bea", seat_id=None, table_id=None, beside=True)), [])["situation"]
    assert "looking pale and feverish" in text


@pytest.mark.parametrize("ailing", [pytest.param(True, id="unwell"), pytest.param(False, id="well")])
def test_an_unwell_guest_is_told_how_they_feel(ailing: bool) -> None:
    observation = view(None, [])
    observation["actor"]["ailing"] = ailing
    told = "They feel feverish and weak tonight; a healer's remedy would help." in brief(observation, [])["situation"]
    assert told is ailing


GIVE = {"id": "give:remedy:bea", "verb": "give", "target_id": "bea", "item": "remedy"}
APPROACH = command("approach", "bea")


@pytest.mark.parametrize("someone, action, said, unsaid", [
    pytest.param(pale("bea"), GIVE, "pale and feverish: this would cure them", "", id="a-remedy-for-the-unwell"),
    pytest.param(person("bea", ailing=False), GIVE, "", "pale", id="a-remedy-for-the-well"),
    pytest.param(pale("bea"), APPROACH, "looks pale and feverish", "", id="a-walk-to-the-unwell"),
    pytest.param(person("bea", ailing=False), APPROACH, "", "pale", id="a-walk-to-the-well"),
])
def test_the_options_say_when_the_remedy_would_help(someone: dict[str, Any], action: dict[str, Any], said: str,
                                                    unsaid: str) -> None:
    text = option_text(healer(someone), action)
    assert (said in text, unsaid in text and bool(unsaid)) == (True, False)


def scored(observation: dict[str, Any], *actions: dict[str, Any]) -> dict[str, float]:
    """Local scores of actions, by ID."""
    return local_scores(observation, list(actions))


def at_another_table(person_id: str, **fields: Any) -> dict[str, Any]:
    """Someone seated at a table across the room."""
    return person(person_id, seat_id="fw", table_id="far", **fields)


@pytest.mark.parametrize("remedies, sick, expected", [
    pytest.param(3, True, True, id="a-healer-goes-to-the-unwell"),
    pytest.param(0, True, False, id="no-remedy-no-errand"),
    pytest.param(3, False, False, id="nobody-unwell"),
])
def test_a_healer_walks_over_to_the_unwell_before_the_well(remedies: int, sick: bool, expected: bool) -> None:
    observation = healer(at_another_table("bea", ailing=sick), at_another_table("cid"), remedies=remedies)
    scores = scored(observation, command("approach", "bea"), command("approach", "cid"))
    assert (scores["approach:bea"] > scores["approach:cid"]) is expected


def test_a_remedy_for_someone_beside_them_beats_everything_else() -> None:
    observation = healer(pale("bea"))
    observation["objects"].append({"id": "door", "kind": "door", "x": 0, "y": 7, "reserved_by": None,
                                   "interaction_spots": [[0, 6]]})
    scores = scored(observation, GIVE, command("sit", "w"), command("leave", "door"), command("talk", "bea"))
    assert max(scores, key=lambda key: scores[key]) == "give:remedy:bea" and scores["give:remedy:bea"] == 0.95


def test_a_remedy_for_a_well_guest_stays_a_small_kindness() -> None:
    scores = scored(healer(person("bea")), GIVE)
    assert scores["give:remedy:bea"] < 0.5


def test_nothing_else_cures_so_nothing_else_gets_the_bonus() -> None:
    keepsake = {**GIVE, "id": "give:keepsake:bea", "item": "keepsake"}
    observation = healer(pale("bea"))
    observation["actor"]["inventory"]["keepsake"] = 1
    assert scored(observation, keepsake)["give:keepsake:bea"] < 0.5


def talk_view(ailing_listener: bool) -> dict[str, Any]:
    """The view of the next turn of Ada and Bea's scene, with Bea (the other speaker) unwell or not."""
    world = seated_talk()
    actor(world, "bea")["ailing"] = ailing_listener
    return turn_view(world, conversation_of(world, "ada"))


@pytest.mark.parametrize("ailing", [pytest.param(True, id="unwell"), pytest.param(False, id="well")])
def test_the_writer_is_told_who_looks_unwell(ailing: bool) -> None:
    content = turn_question(talk_view(ailing))["content"]
    assert ("looks pale and feverish" in content) is ailing


def test_the_writer_is_told_when_the_speaker_is_the_unwell_one() -> None:
    world = seated_talk()
    speaker = next(item for item in world["actors"] if item["id"] == turn_view(world, conversation_of(world, "ada"))["speaker"]["id"])
    speaker["ailing"] = True
    content = turn_question(turn_view(world, conversation_of(world, "ada")))["content"]
    assert "You feel feverish and weak tonight." in content


def event(kind: str, actor_id: str, time: float, message: str = "x") -> dict[str, Any]:
    """A logged event."""
    return {"time": time, "actor_id": actor_id, "type": kind, "message": message}


NAMES = {"ada": "Ada", "bea": "Bea"}


@pytest.mark.parametrize("events, expected", [
    pytest.param([], (None, None, None, None, False), id="nobody-fell-ill"),
    pytest.param([event("arrived_unwell", "bea", 1.0)], ("Bea", 1.0, None, None, True), id="never-cured"),
    pytest.param([event("arrived_unwell", "bea", 1.0), event("cured", "ada", 200.0, "Bea took Ada's remedy"),
                  event("cured", "bea", 200.0, "Bea took Ada's remedy")], ("Bea", 1.0, "Ada", 200.0, False),
                 id="cured-by-ada"),
    pytest.param([event("arrived_unwell", "bea", 1.0), event("cured", "bea", 200.0, "m"), event("cured", "ada", 200.0, "m")],
                 ("Bea", 1.0, "Ada", 200.0, False), id="either-event-first"),
    pytest.param([event("arrived_unwell", "bea", 1.0), event("quarrel", "ada", 5.0)], ("Bea", 1.0, None, None, True),
                 id="other-events-ignored"),
])
def test_the_unwell_guest_and_their_cure_are_counted(events: list[dict[str, Any]], expected: tuple[Any, ...]) -> None:
    found = ailment_counts(events, NAMES)
    assert (found["ailing"], found["arrived_at"], found["cured_by"], found["cured_at"], found["left_ailing"]) == expected
