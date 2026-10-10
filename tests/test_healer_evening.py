"""A healer and an unwell guest alone at the inn: whatever the evening's draws, she hands him a remedy."""

import asyncio
import json
from pathlib import Path
from random import Random
from typing import Any

import pytest

from tavern.evening.lockstep import Pace, run_evening
from tavern.evening.scenario import open_evening, parse_scenario
from tavern.mind.agents import Evaluators
from tavern.mind.cards import parse_cards

ROOT = Path(__file__).parents[1]
CLOSES_AT = 600


async def unasked(view: Any, candidates: Any, config: Any) -> dict[str, float]:
    """No model is asked offline; the local policy decides."""
    raise AssertionError("An offline evening asks no model")


def healer_and_patient() -> dict[str, Any]:
    """Edda, carrying remedies, and Toren, who carries none and so is the one who comes in unwell."""
    guest = {"color": "#e8a86b", "arrives_at": 0}
    return {"closes_at": CLOSES_AT, "last_call_at": CLOSES_AT - 60, "ailment": {"fatigue": 80},
            "arrival": {"needs": {"thirst": [55, 90], "fatigue": [0, 0], "bladder": [0, 25], "social": [15, 65],
                                  "boredom": [5, 35]}},
            "guests": [{**guest, "id": "edda", "name": "Edda", "sprite": "edda", "card": "edda", "carries": {"remedy": 3}},
                       {**guest, "id": "toren", "name": "Toren", "sprite": "toren", "card": "toren"}]}


def cures(seed: int) -> list[str]:
    """Play the evening offline and list who was cured, by the cure events' actors."""
    room = json.loads((ROOT / "data" / "tavern.json").read_text())
    cards = parse_cards([json.loads(path.read_text()) for path in sorted((ROOT / "data" / "characters").glob("*.json"))])
    world = open_evening(room, parse_scenario(healer_and_patient(), cards), seed)
    evening = asyncio.run(run_evening(world, {"temperature": 0.25}, Random(seed), Evaluators(unasked, unasked),
                                      Pace(step=0.25, model_latency=1.0, time_limit=CLOSES_AT)))
    return sorted({item["actor_id"] for item in evening.events if item["type"] == "cured"})


@pytest.mark.parametrize("seed", [pytest.param(seed, id=f"seed-{seed}") for seed in range(5)])
def test_the_healer_hands_the_unwell_guest_a_remedy(seed: int) -> None:
    assert cures(seed) == ["edda", "toren"]
