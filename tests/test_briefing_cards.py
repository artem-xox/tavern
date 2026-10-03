"""The briefing tells who a guest is: their card's occupation, temperament and goal, and their old ties."""

from typing import Any

import pytest

from tavern.agents import build_candidates
from tavern.briefing import brief
from tavern.cards import PARAMS, parse_cards
from tavern.scenario import open_evening, parse_scenario
from tavern.world import observe_actor, observe_people


def card(card_id: str, name: str, temperament: str, goal: str) -> dict[str, Any]:
    """Build a card with the given temperament and goal."""
    return {"id": card_id, "name": name, "sprite": "visitor", "occupation": "salt merchant",
            "background": "Runs wagons from the coast.", "temperament": temperament, "speech": "Measured.",
            "quirks": "Wipes the table.", "secret": "Holds the inn's mortgage.", "goal": goal,
            "params": dict.fromkeys(PARAMS, 0.5)}


def situation(ties: list[dict[str, str]], cast: bool = True) -> str:
    """Brief Ada, inside the door with Bea and Cid, after opening an evening with the given ties."""
    def guest(name: str) -> dict[str, Any]:
        entry = {"id": name.lower(), "name": name, "color": "#a08060", "sprite": "visitor", "arrives_at": 0}
        return {**entry, "card": name.lower()} if cast else {**entry, "traits": {}}
    cards = parse_cards([card("ada", "Ada", "Cool and calculating, never forgets a slight.", "Buy a debt or two."),
                         card("bea", "Bea", "Cheerful.", "Dance."), card("cid", "Cid", "Dour.", "Sleep.")])
    data = {"guests": [guest("Ada"), guest("Bea"), guest("Cid")], "arrival": {"needs": {"thirst": [50, 50]}},
            "closes_at": 300, "relationships": ties}
    hall = {"width": 9, "height": 6, "blocked": [[x, 5] for x in range(9) if x not in (3, 4, 5)], "objects": [
        {"id": "door", "kind": "door", "name": "Door", "x": 4, "y": 5,
         "interaction_spots": [[4, 4], [3, 4], [5, 4]]}]}
    world = open_evening(hall, parse_scenario(data, cards), 1)
    observation = {**observe_actor(world, "ada"), "people": observe_people(world, "ada")}
    return brief(observation, build_candidates(observation))["situation"]


def tie(b: str, kind: str, note: str) -> dict[str, str]:
    """Tie Ada to another guest."""
    return {"a": "ada", "b": b, "kind": kind, "note": note}


@pytest.mark.parametrize("ties, phrase", [
    pytest.param([], "Occupation: salt merchant.", id="occupation"),
    pytest.param([], "Temperament in words: Cool and calculating, never forgets a slight.", id="temperament"),
    pytest.param([], "Their goal tonight: Buy a debt or two.", id="goal"),
    pytest.param([tie("bea", "old friends", "Grew up on the same street.")],
                 "Bea is an old friend of theirs (Grew up on the same street.).", id="single-old-friend"),
    pytest.param([tie("bea", "rivals", "Bea won the ox.")], "Bea is a rival of theirs (Bea won the ox.).",
                 id="single-rival"),
    pytest.param([tie("bea", "rivals", "Bea won the ox."), tie("cid", "rivals", "Cid lost it.")],
                 "Cid is a rival of theirs (Cid lost it.).", id="two-rivals"),
])
def test_briefing_says_who_the_guest_is(ties: list[dict[str, str]], phrase: str) -> None:
    assert phrase in situation(ties)


@pytest.mark.parametrize("phrase", [
    pytest.param("goal tonight", id="no-goal"),
    pytest.param("of theirs", id="no-ties"),
    pytest.param("Temperament in words", id="no-card-temperament"),
])
def test_guest_without_a_card_is_briefed_as_before(phrase: str) -> None:
    assert phrase not in situation([], cast=False)
