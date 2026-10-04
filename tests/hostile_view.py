"""A hand-made observation of a guest with a grudge, shared by the tests of hostile options (helpers, not tests)."""

from typing import Any

from tavern.social.thoughts import THOUGHTS

NOW = 500.0
CALM = {"thirst": 10, "fatigue": 10, "bladder": 10, "social": 10, "boredom": 10}


def thought(kind: str, about: str, ago: float) -> dict[str, Any]:
    """Build a thought of a kind about someone, formed `ago` seconds before now."""
    rule = THOUGHTS[kind]
    return {"kind": kind, "about": about, "text": f"{kind} {about}", "mood": rule.mood, "opinion": rule.opinion,
            "expires_at": NOW - ago + rule.seconds, "source_event": kind}


def person(person_id: str, **fields: Any) -> dict[str, Any]:
    """Build someone Ada sees, seated at her table."""
    return {"id": person_id, "name": person_id.title(), "x": 5, "y": 2, "seat_id": "e", "table_id": "near",
            "beside": False, **fields}


def view(thoughts: list[dict[str, Any]] | None = None, people: list[dict[str, Any]] | None = None,
         temper: float | None = 0.5, drunkenness: float = 0.0, opinion: float = 0.0,
         **fields: Any) -> dict[str, Any]:
    """Build Ada's observation: seated at the near table, calm, with Bea in sight unless `people` says otherwise."""
    traits = {"patience": 0.5, "comfort": 0.5, "curiosity": 0.5, **({} if temper is None else {"temper": temper})}
    relations = {"bea": {"name": "Bea", "opinion": opinion, "familiarity": "acquaintance"}}
    return {"actor": {"id": "ada", "name": "Ada", "x": 2, "y": 2, "seat_id": "w", "favorite_seat_id": "w",
                      "inventory": {"beer": 0}, "needs": dict(CALM), "visit": {"seconds": 120.0, "beers": 1},
                      "traits": traits, "drunkenness": drunkenness, "relations": relations,
                      "thoughts": thoughts if thoughts is not None else []},
            "objects": [{"id": "w", "kind": "chair", "table_id": "near", "x": 2, "y": 2, "interaction_spots": [[2, 2]],
                         "reserved_by": None}],
            "people": [person("bea")] if people is None else people, "visitors": [], "memory": [], "time": NOW,
            **fields}


QUARREL = [thought("quarrel", "bea", 30.0)]
