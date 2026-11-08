"""The loop an evening builds from its ports: both runners bind the same pieces the same way."""

from dataclasses import dataclass
from typing import Any

from tavern.evening.mind_loop import EveningPorts, evening_mind
from tavern.mind.intentions import INTENTION_RULES


@dataclass
class Fakes:
    """Hand-made ports that never run; each is told apart by identity."""

    async def choose(self, observation: Any) -> dict[str, Any]:
        return {}

    async def write(self, view: Any) -> Any:
        return None

    async def stage(self, view: Any) -> list[str]:
        return []

    async def answer(self, observation: Any, invitation: Any, options: Any) -> dict[str, Any]:
        return {}


def ports(fakes: Fakes, with_answer: bool) -> EveningPorts:
    return EveningPorts(choose=fakes.choose, answer=fakes.answer if with_answer else None, write=fakes.write,
                        stage=fakes.stage, intender=None)


def test_evening_mind_binds_every_port() -> None:
    fakes, courier = Fakes(), object()
    mind = evening_mind(courier, ports(fakes, True), INTENTION_RULES)  # type: ignore[arg-type]
    assert (mind.courier, mind.decide, mind.write, mind.answer, mind.stage, mind.intender, mind.rules) == (
        courier, fakes.choose, fakes.write, fakes.answer, fakes.stage, None, INTENTION_RULES)


def test_evening_mind_leaves_the_answer_to_the_line_writer_without_a_port() -> None:
    assert evening_mind(object(), ports(Fakes(), False), INTENTION_RULES).answer is None  # type: ignore[arg-type]
