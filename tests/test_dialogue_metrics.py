"""How lively a talk between two guests was: repeats, echoes, new ground, variety, staying on their brief."""

from typing import Any

import pytest

from tavern.evening.dialogue_metrics import dialogue_metrics, missed_thresholds, pair_transcript, talk_window

PAIR = {"putin": "Vladimir Putin", "zelensky": "Volodymyr Zelenskyy"}
NAMES = {**PAIR, "hob": "Hob"}
BRIEF = {"putin": ("operation", "west"), "zelensky": ("kyiv", "drones")}


def said(speaker: str, line: str, act: str = "complain", to: str | None = None) -> dict[str, Any]:
    """A `turn` event, worded as the world logs it."""
    listener = to or next(item for item in PAIR if item != speaker)
    return {"type": "turn", "actor_id": speaker, "time": 0.0,
            "message": f"{NAMES[speaker]} to {NAMES[listener]} ({act}): {line}"}


def failed(speaker: str) -> dict[str, Any]:
    """A `turn_failed` event about a speaker."""
    return {"type": "turn_failed", "actor_id": None, "time": 0.0,
            "message": f"A line for {NAMES[speaker]} failed (too long); a scripted one stands in"}


LIVELY = [said("zelensky", "Your drones hit Kyiv again last night, Vladimir."),
          said("putin", "A special operation answers provocations. Ask the Western press who started it.", "disagree"),
          said("zelensky", "Children in Kyiv shelters are no provocation. Name one school we shelled.", "insult")]
ECHOING = [said("zelensky", "You sell tonic from every stage, Vladimir."),
           said("putin", "Tonic from every stage? You sell tonic, Volodymyr."),
           said("zelensky", "Tonic and stages, Vladimir, you sell tonic.")]


@pytest.mark.parametrize("events, expected", [
    pytest.param([], {"lines": 0, "balance": 0.0, "repeated": 0.0, "echo": 0.0, "novelty": 0.0, "variety": 0.0,
                      "on_brief": 0.0, "fallbacks": 0}, id="no-talk"),
    pytest.param([said("zelensky", "Your drones hit Kyiv again.")],
                 {"lines": 1, "balance": 0.0, "repeated": 0.0, "echo": 0.0, "novelty": 1.0, "variety": 1.0,
                  "on_brief": 1.0, "fallbacks": 0}, id="a-single-line"),
    pytest.param([said("zelensky", "Your drones hit Kyiv again."), said("putin", "Hm."),
                  said("zelensky", "Your drones hit Kyiv again!")],
                 {"lines": 3, "balance": 1 / 3, "repeated": 1 / 3, "echo": 0.0, "novelty": 2 / 3, "variety": 1 / 3,
                  "on_brief": 2 / 3, "fallbacks": 0}, id="a-line-said-twice"),
    pytest.param([said("zelensky", "Evening, Hob!", "greet", to="hob"), said("hob", "Evening.", "greet", to="zelensky"),
                  failed("hob")],
                 {"lines": 0, "balance": 0.0, "repeated": 0.0, "echo": 0.0, "novelty": 0.0, "variety": 0.0,
                  "on_brief": 0.0, "fallbacks": 0}, id="talk-with-someone-else-does-not-count"),
    pytest.param([*LIVELY, failed("putin")],
                 {"lines": 3, "balance": 1 / 3, "repeated": 0.0, "echo": 0.0, "novelty": 1.0, "variety": 1.0,
                  "on_brief": 1.0, "fallbacks": 1}, id="a-lively-quarrel"),
])
def test_dialogue_metrics_measure_the_pair(events: list[dict[str, Any]], expected: dict[str, float]) -> None:
    assert dialogue_metrics(events, PAIR, BRIEF) == pytest.approx(expected)


def test_an_echoing_talk_scores_worse_than_a_lively_one() -> None:
    lively, echoing = dialogue_metrics(LIVELY, PAIR, BRIEF), dialogue_metrics(ECHOING, PAIR, BRIEF)
    assert (echoing["echo"] > lively["echo"], echoing["novelty"] < lively["novelty"]) == (True, True)


@pytest.mark.parametrize("events, pair", [
    pytest.param([{"type": "turn", "actor_id": "putin", "time": 0.0, "message": "Vladimir Putin mutters"}], PAIR,
                 id="a-turn-worded-otherwise"),
    pytest.param([], {"putin": "Vladimir Putin"}, id="a-pair-of-one"),
])
def test_dialogue_metrics_reject_bad_input(events: list[dict[str, Any]], pair: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        dialogue_metrics(events, pair, BRIEF)


def at(event: dict[str, Any], time: float) -> dict[str, Any]:
    """The event at a game time."""
    return {**event, "time": time}


@pytest.mark.parametrize("events, kept", [
    pytest.param([], [], id="no-events"),
    pytest.param([at(said("zelensky", "Evening, Hob.", "greet", to="hob"), 5.0)], [], id="no-line-between-the-pair"),
    pytest.param([at(said("zelensky", "Evening, Hob.", "greet", to="hob"), 5.0), at(LIVELY[0], 10.0),
                  at(failed("putin"), 40.0), at(LIVELY[1], 70.0), at(LIVELY[2], 71.0)], [10.0, 40.0, 70.0],
                 id="from-the-pairs-first-line-for-the-window"),
])
def test_the_window_starts_at_the_pairs_first_line(events: list[dict[str, Any]], kept: list[float]) -> None:
    assert [event["time"] for event in talk_window(events, PAIR, 60.0)] == kept


def test_the_transcript_names_the_speaker_and_act_of_each_line_between_the_pair() -> None:
    events = [said("zelensky", "Evening, Hob.", "greet", to="hob"), *LIVELY[:2]]
    assert pair_transcript(events, PAIR) == [
        "Volodymyr Zelenskyy (complain): Your drones hit Kyiv again last night, Vladimir.",
        "Vladimir Putin (disagree): A special operation answers provocations. Ask the Western press who started it."]


@pytest.mark.parametrize("values, missed", [
    pytest.param({}, [], id="nothing-measured-nothing-missed"),
    pytest.param({"echo": 0.2, "lines": 8}, [], id="within-both-bounds"),
    pytest.param({"echo": 0.5, "lines": 3}, ["echo 0.5 > 0.35", "lines 3 < 6"], id="over-and-under"),
    pytest.param({"echo": 0.35, "lines": 6}, [], id="bounds-included"),
])
def test_thresholds_name_every_metric_out_of_bounds(values: dict[str, float], missed: list[str]) -> None:
    assert missed_thresholds(values, {"echo": {"max": 0.35}, "lines": {"min": 6}, "novelty": {"min": 0.5}}) == missed


def test_a_threshold_without_a_bound_is_rejected() -> None:
    with pytest.raises(ValueError):
        missed_thresholds({"echo": 0.1}, {"echo": {"most": 0.3}})
