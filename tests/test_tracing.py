"""Model calls are traced to LangSmith: each character's calls of one evening form one thread."""

import asyncio
from typing import Any

import pytest

from tavern.adapters.claude import ClaudeError
from tavern.adapters.jev import JevError, request_body
from tavern.adapters.tracing import (Tracer, open_tracer, traced_intender, traced_question, traced_scores,
                                     traced_writer)
from tavern.mind.haiku_turns import RejectedTurn

WAIT = {"id": "wait", "verb": "wait", "target_id": None}
SIT = {"id": "sit-chair-1", "verb": "sit", "target_id": "chair-1"}
JEV = {"typesafe_api_key": "jev-secret", "model": "jev-latest", "timeout": 2.0}
QUESTION = {"system": ["Shared rules.", "Card of the speaker."], "content": "The moment.",
            "schema": {"type": "object"}, "max_tokens": 50}
LINE = {"line": "Evening, friend.", "act": "greet", "addressee": None, "topic": "the road"}
CLAUDE_USAGE = {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 300,
                "cache_creation_input_tokens": 20}


class FakeLangSmith:
    """Keeps the runs a LangSmith client would upload, by run ID."""

    def __init__(self) -> None:
        self.runs: dict[Any, dict[str, Any]] = {}

    def create_run(self, **run: Any) -> None:
        self.runs[run["id"]] = dict(run)

    def update_run(self, run_id: Any, **update: Any) -> None:
        # As the API does, a field the update leaves empty keeps what the run was created with.
        self.runs[run_id].update({field: value for field, value in update.items() if value is not None})


def tracer() -> Tracer:
    return Tracer(FakeLangSmith(), "tavern", "evening-0")  # type: ignore[arg-type]


def named(traces: Tracer, name: str) -> list[dict[str, Any]]:
    return [run for run in traces.client.runs.values() if run["name"] == name]  # type: ignore[attr-defined]


def thread(run: dict[str, Any]) -> str | None:
    return run["extra"]["metadata"].get("session_id")


def scorer(usage: dict[str, int] | None = None, error: Exception | None = None):
    async def evaluate(view, candidates, config):
        if error is not None:
            raise error
        return {action["id"]: 0.5 for action in candidates}, usage
    return evaluate


def score(traces: Tracer, guest: str, stage: str = "actions", candidate: dict[str, Any] = WAIT,
          usage: dict[str, int] | None = None, error: Exception | None = None) -> Any:
    view = {"self": {"name": guest}}
    return asyncio.run(traced_scores(stage, scorer(usage, error), traces)(view, [candidate], JEV))


def claude(answer: dict[str, Any] | None = None, usage: dict[str, int] | None = CLAUDE_USAGE,
           error: Exception | None = None):
    async def ask(question):
        if error is not None:
            raise error
        return answer or {"line": "Evening, friend."}, usage
    return ask


def speak(traces: Tracer, speaker: str, ask=None, written: Any = None) -> Any:
    asked = traced_question(ask or claude(), "claude-haiku-4-5", traces)

    async def write(view, config):
        answer = (await asked(QUESTION))[0]
        if written is not None:
            raise written
        return {**LINE, "line": answer["line"]}
    return asyncio.run(traced_writer(write, traces)({"speaker": {"id": speaker.lower(), "name": speaker}},
                                                     {"typesafe_api_key": "jev-secret"}))


@pytest.mark.parametrize("guests, threads", [
    pytest.param([], [], id="no-calls"),
    pytest.param(["Edda"], ["evening-0 · Edda"], id="single-guest"),
    pytest.param(["Edda", "Edda"], ["evening-0 · Edda", "evening-0 · Edda"], id="same-guest-twice"),
    pytest.param(["Edda", "Calder"], ["evening-0 · Calder", "evening-0 · Edda"], id="two-guests"),
])
def test_each_guest_scores_land_in_the_guests_thread_of_the_evening(guests, threads):
    traces = tracer()
    for guest in guests:
        score(traces, guest)
    assert sorted(thread(run) for run in named(traces, "jev.actions")) == threads


@pytest.mark.parametrize("stage, candidate, seats", [
    pytest.param("actions", WAIT, False, id="first-stage"),
    pytest.param("family", WAIT, False, id="within-a-family"),
    pytest.param("seats", SIT, True, id="chairs"),
])
def test_a_jev_run_carries_the_exact_request_and_the_scores(stage, candidate, seats):
    traces = tracer()
    scores = score(traces, "Edda", stage, candidate, usage={"input_tokens": 900, "output_tokens": 12})
    [run] = named(traces, f"jev.{stage}")
    assert (run["run_type"], run["inputs"], run["outputs"]) == (
        "llm", request_body({"self": {"name": "Edda"}}, [candidate], "jev-latest", seats),
        {"scores": scores[0], "usage_metadata": {"input_tokens": 900, "output_tokens": 12, "total_tokens": 912,
                                                 "input_token_details": {"cache_read": 0, "cache_creation": 0}}})


def test_a_jev_run_without_reported_usage_shows_only_the_scores():
    traces = tracer()
    score(traces, "Edda")
    assert named(traces, "jev.actions")[0]["outputs"] == {"scores": {"wait": 0.5}}


def test_no_run_holds_an_api_key():
    traces = tracer()
    score(traces, "Edda")
    speak(traces, "Edda")
    assert "secret" not in repr(traces.client.runs)  # type: ignore[attr-defined]


def test_a_failed_jev_call_is_traced_as_an_error_and_raised_again():
    traces = tracer()
    with pytest.raises(JevError, match="Jev HTTP 500"):
        score(traces, "Edda", error=JevError("Jev HTTP 500"))
    assert "Jev HTTP 500" in named(traces, "jev.actions")[0]["error"]


def test_a_line_is_a_turn_in_the_speakers_thread_with_the_haiku_prompt_beneath_it():
    traces = tracer()
    result = speak(traces, "Calder")
    [turn], [haiku] = named(traces, "turn"), named(traces, "claude-haiku-4-5")
    assert (thread(turn), turn["outputs"], thread(haiku), haiku["parent_run_id"], haiku["run_type"]) == (
        "evening-0 · Calder", result, "evening-0 · Calder", turn["id"], "llm")


def test_a_haiku_run_carries_the_prompt_answer_and_cached_tokens():
    traces = tracer()
    speak(traces, "Calder")
    [haiku] = named(traces, "claude-haiku-4-5")
    assert (haiku["inputs"], haiku["outputs"]) == (
        {"messages": [{"role": "system", "content": "Shared rules."},
                      {"role": "system", "content": "Card of the speaker."},
                      {"role": "user", "content": "The moment."}],
         "schema": {"type": "object"}, "max_tokens": 50},
        {"answer": {"line": "Evening, friend."},
         "usage_metadata": {"input_tokens": 330, "output_tokens": 5, "total_tokens": 335,
                            "input_token_details": {"cache_read": 300, "cache_creation": 20}}})


@pytest.mark.parametrize("ask, written, error", [
    pytest.param(claude(error=ClaudeError("Claude HTTP 529")), None, ClaudeError, id="claude-fails"),
    pytest.param(claude(), RejectedTurn("A line is one short spoken line"), RejectedTurn, id="line-rejected"),
])
def test_a_turn_that_fails_is_traced_as_an_error_and_raised_again(ask, written, error):
    traces = tracer()
    with pytest.raises(error):
        speak(traces, "Calder", ask, written)
    assert named(traces, "turn")[0]["error"]


def test_an_intention_is_a_run_in_the_guests_thread():
    traces = tracer()
    asked = traced_question(claude({"thought": "Cold night.", "intention": "Warm up by the fire."}),
                            "claude-haiku-4-5", traces)

    async def intend(view):
        answer = (await asked(QUESTION))[0]
        return {"thought": answer["thought"], "intention": answer["intention"]}
    written = asyncio.run(traced_intender(intend, traces)({"actor_id": "edda", "name": "Edda", "time": 30.0}))
    [intention], [haiku] = named(traces, "intention"), named(traces, "claude-haiku-4-5")
    assert (thread(intention), intention["inputs"], intention["outputs"], haiku["parent_run_id"]) == (
        "evening-0 · Edda", {"actor_id": "edda", "name": "Edda", "time": 30.0}, written, intention["id"])


def test_a_question_outside_any_characters_call_belongs_to_no_thread():
    traces = tracer()
    asyncio.run(traced_question(claude(), "claude-haiku-4-5", traces)(QUESTION))
    [haiku] = named(traces, "claude-haiku-4-5")
    assert (thread(haiku), haiku.get("parent_run_id")) == (None, None)


@pytest.mark.parametrize("call", [
    pytest.param(lambda traces: asyncio.run(traced_scores("actions", scorer(), traces)({"self": {}}, [WAIT], JEV)),
                 id="jev-view-without-a-name"),
    pytest.param(lambda traces: asyncio.run(traced_scores("stools", scorer(), traces)(
        {"self": {"name": "Edda"}}, [WAIT], JEV)), id="unknown-stage"),
    pytest.param(lambda traces: asyncio.run(traced_writer(None, traces)({"speaker": {"name": " "}}, {})),  # type: ignore[arg-type]
                 id="blank-speaker"),
    pytest.param(lambda traces: asyncio.run(traced_intender(None, traces)({"actor_id": "edda"})),  # type: ignore[arg-type]
                 id="intention-view-without-a-name"),
])
def test_a_call_without_a_character_or_stage_is_rejected(call):
    with pytest.raises(ValueError):
        call(tracer())


@pytest.mark.parametrize("values, project", [
    pytest.param({"LANGSMITH_API_KEY": "ls-key"}, "tavern", id="default-project"),
    pytest.param({"LANGSMITH_API_KEY": "ls-key", "LANGSMITH_PROJECT": ""}, "tavern", id="blank-project"),
    pytest.param({"LANGSMITH_API_KEY": "ls-key", "LANGSMITH_PROJECT": "inn-tests"}, "inn-tests", id="named-project"),
])
def test_a_tracer_sends_to_the_configured_project_for_one_evening(values, project):
    traces = open_tracer(values, "evening-0")
    assert (traces.project, traces.evening) == (project, "evening-0")


@pytest.mark.parametrize("values, evening", [
    pytest.param({}, "evening-0", id="no-key"),
    pytest.param({"LANGSMITH_API_KEY": "  "}, "evening-0", id="blank-key"),
    pytest.param({"LANGSMITH_API_KEY": None}, "evening-0", id="key-left-empty-in-env-file"),
    pytest.param({"LANGSMITH_API_KEY": "ls-key"}, " ", id="blank-evening"),
])
def test_a_tracer_needs_a_key_and_an_evening(values, evening):
    with pytest.raises(ValueError):
        open_tracer(values, evening)
