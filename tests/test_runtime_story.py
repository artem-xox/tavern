"""The live runtime keeps the evening's story score and, when the last guest leaves, has the storyteller retell it."""

import asyncio
import re
from pathlib import Path
from typing import Any

from tavern.evening.scenario import Scenario, parse_scenario
from tavern.server.runtime import TavernRuntime



def hall() -> dict[str, Any]:
    """Build a 9×6 hall with a door in the bottom wall and a tap."""
    return {"width": 9, "height": 6, "blocked": [[x, 5] for x in range(9) if x != 4], "objects": [
        {"id": "door", "kind": "door", "name": "Door", "x": 4, "y": 5, "interaction_spots": [[4, 4]]},
        {"id": "tap", "kind": "tap", "name": "Tap", "x": 1, "y": 0, "interaction_spots": [[1, 1]], "stock": 5},
    ]}


def plan() -> Scenario:
    """Expect one guest, Ada, at once, before closing at 300 s."""
    guest = {"id": "ada", "name": "Ada", "color": "#a08060", "sprite": "visitor", "traits": {}, "arrives_at": 0}
    return parse_scenario({"guests": [guest], "arrival": {"needs": {"thirst": [40, 80]}}, "closes_at": 300})


def storyteller(failure: Exception | None = None) -> Any:
    """A fake storyteller port: it cites the first line it is shown (and keeps that number as `cited`), or raises."""
    cited: list[int] = []

    async def ask(question: Any) -> Any:
        if failure is not None:
            raise failure
        cited.append(int(re.search(r"\[#(\d+)", question["content"]).group(1)))  # type: ignore[union-attr]
        return {"title": "The Nap of Ada 💤", "chapters": [{"text": "Ada came in. 🍺", "events": cited[-1:]}]}
    ask.cited = cited  # type: ignore[attr-defined]
    return ask


def runtime(tmp_path: Path, ask: Any = None) -> TavernRuntime:
    """Open a running scenario evening with one guest."""
    opened = TavernRuntime(hall(), tmp_path / "save.json", {"typesafe_api_key": None}, scenario=plan(), storyteller=ask)
    opened.world["paused"] = False
    return opened


def last_guest_leaves(opened: TavernRuntime) -> None:
    opened.advance(0.1)
    opened.world["departed"].append(opened.world["actors"].pop())
    opened.advance(0.1)


def test_snapshot_counts_the_moments_as_they_are_logged(tmp_path: Path) -> None:
    async def evening() -> Any:
        opened = runtime(tmp_path)
        opened.advance(0.1)
        for time in (1.0, 2.0):
            opened.world["events"].append({"time": time, "actor_id": "ada", "type": "dozed_off", "message": f"nap {time}"})
        opened.advance(0.1)
        return opened.snapshot()["story"]

    story = asyncio.run(evening())
    assert story["moments"]["fell_asleep"] == 2 and story["score"] == 4.0


def test_a_moment_is_counted_once_however_often_the_snapshot_is_taken(tmp_path: Path) -> None:
    async def evening() -> int:
        opened = runtime(tmp_path)
        opened.world["events"].append({"time": 1.0, "actor_id": "ada", "type": "gave", "message": "Ada gave Bea a beer"})
        for _ in range(3):
            opened.advance(0.1)
        return opened.snapshot()["story"]["moments"]["gift"]

    assert asyncio.run(evening()) == 1


def test_a_new_evening_starts_a_new_score(tmp_path: Path) -> None:
    async def evening() -> Any:
        opened = runtime(tmp_path)
        opened.world["events"].append({"time": 1.0, "actor_id": "ada", "type": "dozed_off", "message": "nap"})
        opened.advance(0.1)
        opened.command({"type": "reset"})
        return opened.snapshot()

    snapshot = asyncio.run(evening())
    assert snapshot["story"]["score"] == 0.0 and snapshot["retelling"] is None


def test_the_storyteller_retells_the_evening_when_it_is_over(tmp_path: Path) -> None:
    async def evening() -> Any:
        ask = storyteller()
        opened = runtime(tmp_path, ask)
        last_guest_leaves(opened)
        before = opened.snapshot()["retelling"]
        waiting = opened.snapshot()["telling"]
        await opened.await_retelling()
        who = [opened.chronicle[ask.cited[0]]["actor_id"]]
        return before, waiting, opened.snapshot()["telling"], opened.snapshot()["retelling"], ask.cited[0], who

    before, waiting, telling, retelling, cited, who = asyncio.run(evening())
    assert (before, waiting, telling) == (None, True, False)
    assert retelling == {"title": "The Nap of Ada 💤", "chapters": [
        {"text": "Ada came in. 🍺", "events": [cited], "actors": [actor for actor in who if actor is not None]}]}


def test_a_storyteller_that_fails_leaves_the_evening_unretold_and_says_so(tmp_path: Path) -> None:
    async def evening() -> tuple[Any, str]:
        opened = runtime(tmp_path, storyteller(ValueError("A retelling's title must be a nonempty string")))
        last_guest_leaves(opened)
        await opened.await_retelling()
        return opened.snapshot()["retelling"], opened.world["events"][-1]["message"]

    retelling, said = asyncio.run(evening())
    assert retelling is None and "could not be retold" in said and "nonempty string" in said


def test_without_a_storyteller_the_evening_ends_unretold(tmp_path: Path) -> None:
    async def evening() -> Any:
        opened = runtime(tmp_path)
        last_guest_leaves(opened)
        return opened.snapshot()["retelling"]

    assert asyncio.run(evening()) is None


def test_the_evening_is_not_being_retold_before_it_ends(tmp_path: Path) -> None:
    async def evening() -> bool:
        opened = runtime(tmp_path, storyteller())
        opened.advance(0.1)
        return opened.snapshot()["telling"]

    assert asyncio.run(evening()) is False
