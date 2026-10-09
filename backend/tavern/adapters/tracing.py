"""LangSmith traces of the model calls: each character's calls of one evening form one thread."""

from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Literal

from langsmith import Client, trace, tracing_context
from langsmith.run_trees import RunTree

from tavern.adapters.jev import request_body
from tavern.evening.recording import MeteredAsk
from tavern.mind.intentions import Intender, Written
from tavern.mind.questions import Question
from tavern.social.turns import TurnResult, TurnWriter

DEFAULT_ENDPOINT = "https://api.smith.langchain.com"
DEFAULT_PROJECT = "tavern"
# The decision stages Jev scores (`agents.Evaluators`); only `seats` asks the seat question.
_STAGES = ("actions", "seats", "family", "aims")

# A metered Jev evaluator (`jev.evaluate_actions_metered`): the scores and the usage it reported.
Scorer = Callable[[Mapping[str, Any], Sequence[Mapping[str, Any]], Mapping[str, Any]],
                  Awaitable[tuple[dict[str, float], Mapping[str, Any] | None]]]


@dataclass(frozen=True)
class Tracer:
    """Where runs go: a LangSmith client and project, and the evening whose threads they join."""

    client: Client
    project: str
    evening: str


def open_tracer(values: Mapping[str, Any], evening: str) -> Tracer:
    """Connect to LangSmith for one evening.

    Args:
        values: Environment or env-file values: `LANGSMITH_API_KEY`, and optionally
            `LANGSMITH_ENDPOINT` and `LANGSMITH_PROJECT` (empty means the default).
        evening: Label of the evening; each character's thread is named after it.

    Returns:
        The tracer every traced port of the evening shares.

    Raises:
        ValueError: The API key or the evening label is missing or blank.
    """
    key = values.get("LANGSMITH_API_KEY")
    if not isinstance(key, str) or not key.strip():
        raise ValueError("Tracing needs LANGSMITH_API_KEY")
    if not evening.strip():
        raise ValueError("Tracing needs an evening label")
    client = Client(api_url=values.get("LANGSMITH_ENDPOINT") or DEFAULT_ENDPOINT, api_key=key)
    return Tracer(client, values.get("LANGSMITH_PROJECT") or DEFAULT_PROJECT, evening)


def traced_scores(stage: str, evaluate: Scorer, tracer: Tracer) -> Scorer:
    """Trace each Jev scoring as an LLM run in the guest's thread.

    Args:
        stage: Decision stage the evaluator serves: `actions`, `seats`, `family` or `aims`.
        evaluate: Metered Jev evaluator, e.g. `jev.evaluate_actions_metered`.
        tracer: Where the runs go.

    Returns:
        An evaluator answering as `evaluate` does; its run holds the exact request body (the
        prompts), the scores and the token usage, or the error it raised again.

    Raises:
        ValueError: The stage is unknown; the returned evaluator raises it for a view whose
            `self` has no name.
    """
    if stage not in _STAGES:
        raise ValueError(f"Unknown Jev stage {stage!r}; expected one of {_STAGES}")

    async def traced(view: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
                     config: Mapping[str, Any]) -> tuple[dict[str, float], Mapping[str, Any] | None]:
        guest = _name(view.get("self"), "A Jev view's self")
        prompt = request_body(view, candidates, config.get("model", ""), stage == "seats", stage == "aims")
        with _run(tracer, f"jev.{stage}", "llm", prompt, guest, _model("typesafe", prompt["model"])) as run:
            scores, usage = await evaluate(view, candidates, config)
            run.end(outputs={"scores": scores, **_usage(usage)})
        return scores, usage
    return traced


def traced_question(ask: MeteredAsk, model: str, tracer: Tracer) -> MeteredAsk:
    """Trace each Claude question as an LLM run, beneath the turn or intention that asks it.

    Args:
        ask: Metered Claude port, e.g. `claude.ask_claude` bound to its config.
        model: Claude model the port asks, for LangSmith's cost.
        tracer: Where the runs go.

    Returns:
        A port answering as `ask` does; its run holds the system blocks and content as
        messages, the schema, the answer and the token usage with cache reads and writes.
        Asked outside a traced turn or intention (a card), the run belongs to no thread.
    """
    async def traced(question: Question) -> tuple[dict[str, Any], Mapping[str, int] | None]:
        messages = [*({"role": "system", "content": block} for block in question["system"]),
                    {"role": "user", "content": question["content"]}]
        prompt = {"messages": messages, "schema": question["schema"], "max_tokens": question["max_tokens"]}
        with _run(tracer, model, "llm", prompt, None, _model("anthropic", model)) as run:
            answer, usage = await ask(question)
            run.end(outputs={"answer": answer, **_usage(usage)})
        return answer, usage
    return traced


def traced_writer(writer: TurnWriter, tracer: Tracer) -> TurnWriter:
    """Trace each written line as a `turn` run in the speaker's thread.

    Args:
        writer: Turn writer whose model port is traced with `traced_question`.
        tracer: Where the runs go.

    Returns:
        A writer answering as `writer` does; its run holds the scene view and the checked
        line, or the rejection it raised again.

    Raises:
        ValueError: The returned writer raises it for a view whose speaker has no name.
    """
    async def traced(view: Mapping[str, Any], config: Mapping[str, Any]) -> TurnResult:
        with _run(tracer, "turn", "chain", view, _name(view.get("speaker"), "A turn view's speaker")) as run:
            result = await writer(view, config)
            run.end(outputs=dict(result))
        return result
    return traced


def traced_intender(intender: Intender, tracer: Tracer) -> Intender:
    """Trace each intention as an `intention` run in the guest's thread.

    Args:
        intender: Mind port whose model port is traced with `traced_question`.
        tracer: Where the runs go.

    Returns:
        An intender answering as `intender` does; its run holds the guest's view and the
        thought and intention written, or the error raised again.

    Raises:
        ValueError: The returned intender raises it for a view without the guest's name.
    """
    async def traced(view: Mapping[str, Any]) -> Written:
        with _run(tracer, "intention", "chain", view, _name(view, "An intention view")) as run:
            written = await intender(view)
            run.end(outputs=dict(written))
        return written
    return traced


def _name(person: Any, what: str) -> str:
    name = person.get("name") if isinstance(person, Mapping) else None
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"{what} needs a name to trace, not {person!r}")
    return name


def _model(provider: str, name: str) -> dict[str, str]:
    # The metadata keys LangSmith reads to price a run.
    return {"ls_provider": provider, "ls_model_name": name}


def _usage(usage: Mapping[str, Any] | None) -> dict[str, Any]:
    # LangSmith counts cached prompt tokens as input, detailed apart; Claude reports them apart
    # and Jev has no cache, so a counter left out is zero.
    if usage is None:
        return {}
    read, written = usage.get("cache_read_input_tokens", 0), usage.get("cache_creation_input_tokens", 0)
    prompt = usage["input_tokens"] + read + written
    return {"usage_metadata": {"input_tokens": prompt, "output_tokens": usage["output_tokens"],
                               "total_tokens": prompt + usage["output_tokens"],
                               "input_token_details": {"cache_read": read, "cache_creation": written}}}


@contextmanager
def _run(tracer: Tracer, name: str, kind: Literal["llm", "chain"], inputs: Mapping[str, Any], character: str | None,
         metadata: Mapping[str, str] | None = None) -> Iterator[RunTree]:
    # Tracing is switched on here, per run, so LANGSMITH_TRACING in the environment plays no part.
    # A run inside another (a question inside a turn) inherits its thread from that parent.
    thread = {} if character is None else {"session_id": f"{tracer.evening} · {character}",
                                           "evening": tracer.evening, "character": character}
    with tracing_context(enabled=True, client=tracer.client, project_name=tracer.project), \
            trace(name, kind, inputs=dict(inputs), metadata={**thread, **(metadata or {})},
                  client=tracer.client, project_name=tracer.project) as run:
        yield run
