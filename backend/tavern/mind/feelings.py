"""A visitor's inner state as others read it: mood, opinions and drink in words, and the inspector's view."""

from collections.abc import Mapping
from typing import Any, TypedDict

from tavern.body.drunkenness import drunk_stage, speech_instruction
from tavern.social.thoughts import THOUGHTS, Thought, active_thoughts, mood, opinion_of


class Opinion(TypedDict):
    """What a visitor thinks of one person, for the inspector."""

    id: str
    name: str
    opinion: float
    familiarity: str


class Mind(TypedDict):
    """A visitor's inner state for the inspector and the scene.

    Derived mood, active thoughts and opinions; drunkenness with its stage, and how far the
    client sways their sprite.
    """

    mood: float
    thoughts: list[Thought]
    opinions: list[Opinion]
    drunkenness: float
    stage: str
    sway: float


def feelings(observation: Mapping[str, Any]) -> str:
    """Put a visitor's mood, opinions, lingering grievances and drink into words for the briefing.

    Args:
        observation: Personal observation; its actor may lack thoughts, relations and
            drunkenness when built outside the world (they read as none, and sober), and
            without a `time` every thought still counts.

    Returns:
        Sentences such as "They are in a sour mood. They dislike Bea, who took their seat."
    """
    actor, now = observation["actor"], observation.get("time", float("-inf"))
    grievances = actor.get("visit", {}).get("grievances", [])
    parts = [f"They are {_mood_words(mood(actor, now))}.", *_opinions(actor, now),
             f"Still rankling tonight: {'; '.join(grievances)}." if grievances else "",
             speech_instruction(actor.get("drunkenness", 0.0))]
    return " ".join(part for part in parts if part)


def _mood_words(value: float) -> str:
    # A taken seat (−6) sours an even mood; two wrongs make it foul.
    return ("in high spirits" if value >= 8 else "in a good mood" if value >= 3 else "in an even mood" if value > -3
            else "in a sour mood" if value > -10 else "in a foul mood")


def _opinions(actor: Mapping[str, Any], now: float) -> list[str]:
    # People they barely care about (|opinion| < 10) go unmentioned, unless they are friends.
    sentences = []
    for other, relation in actor.get("relations", {}).items():
        value = opinion_of(actor, other, now)
        if abs(value) < 10 and relation["familiarity"] != "friend":
            continue
        verb = "loathe" if value <= -40 else "dislike" if value < 0 else "like" if value >= 10 else "know"
        sentences.append(f"They {verb} {relation['name']}{_why(actor, other, value, relation, now)}.")
    return sentences


def _why(actor: Mapping[str, Any], other: str, value: float, relation: Mapping[str, Any], now: float) -> str:
    # The latest thought that pulls the same way explains the opinion; an old friend needs no reason.
    if relation["familiarity"] == "friend" and value >= 0:
        return ", an old friend"
    reasons = [item for item in active_thoughts(actor.get("thoughts", []), now)
               if item["about"] == other and (item["opinion"] < 0) == (value < 0)]
    return f", who {THOUGHTS[reasons[-1]['kind']].reason}" if reasons else ""


def minds(world: Mapping[str, Any]) -> dict[str, Mind]:
    """Describe every visitor's inner state for the inspector, the departed included.

    Args:
        world: Current world; it is not modified.

    Returns:
        Per visitor ID: derived mood, active thoughts oldest first, opinions of everyone
        they have a relation with in relation order, drunkenness, its stage and the sprite's
        sway. Unrounded; the client formats them.
    """
    now = world["time"]
    return {actor["id"]: Mind(
        mood=mood(actor, now), thoughts=[Thought(**item) for item in active_thoughts(actor["thoughts"], now)],
        opinions=[Opinion(id=other, name=relation["name"], opinion=opinion_of(actor, other, now),
                          familiarity=relation["familiarity"]) for other, relation in actor["relations"].items()],
        drunkenness=actor["drunkenness"], stage=drunk_stage(actor["drunkenness"]).name,
        sway=drunk_stage(actor["drunkenness"]).sway)
        for actor in [*world["actors"], *world["departed"]]}
