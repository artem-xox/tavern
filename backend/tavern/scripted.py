"""Scripted conversation lines: the offline turn writer, choosing a speech act by a seeded rule."""

from collections.abc import Mapping
from random import Random
from types import MappingProxyType
from typing import Any

# Lines stay under 38 characters, so each reads in the minimum gap; {name} is the addressee.
LINES: Mapping[str, tuple[str, ...]] = MappingProxyType({
    "greet": ("Evening, {name}!", "Well met, {name}.", "Room for one more, {name}?"),
    "small_talk": ("Cold on the road tonight.", "Busy night for the inn.", "Heard the pass is snowed in.",
                   "Fine fire they keep here."),
    "joke": ("My mule drinks less than me.", "This ale could raise the dead.", "Came for one. Still here."),
    "complain": ("This ale tastes of old boots.", "Too loud in here, {name}.", "You never listen, {name}."),
    "content": ("Good talk. I'll let you be.", "Well, I'll leave you to it."),
    "pressed": ("Excuse me, I must step out.", "Pardon me a moment."),
})
PLACE_LINES: Mapping[str, str] = MappingProxyType({
    "tap": "The ale's at the tap, by the bar.", "toilet": "The WC is past the tables.",
    "darts": "There's a darts board here."})

PRESSING = 75.0  # A thirst, tiredness or bladder this strong takes a guest out of any conversation.
CONTENT = 25.0  # Below this wish for company, a guest has had enough talk.
JOKES = 0.3  # Share of friendly lines that are jokes.


def scripted_turn(view: Mapping[str, Any]) -> dict[str, Any]:
    """Write the next line of a scene by a seeded rule, without a model.

    The first line greets. A speaker pressed by a need says goodbye, and so does one with company
    enough once they have said something besides a greeting.
    Otherwise they may complain once (more likely the more beers past the first and the less
    patience), then tell where the places they know are, once, then make small talk or joke.

    Args:
        view: Scene view of `turns.turn_view`.

    Returns:
        A turn result (`turns.TurnResult`) addressing the next participant in the circle, on
        the scene's topic. The draw is seeded by the evening, the scene and the turn index, so a
        replay writes the same line.

    Raises:
        KeyError: The view lacks a field the rule reads.
    """
    scene, me = view["conversation"], view["speaker"]
    rng = Random(f"{view['seed']}:{scene['id']}:{scene['turn']}")
    act, kind = _act(scene, me, rng)
    people = [item for item in scene["participants"] if item["id"] != me["id"]]
    ids = [item["id"] for item in scene["participants"]]
    addressee = scene["participants"][(ids.index(me["id"]) + 1) % len(ids)] if me["id"] in ids else people[0]
    # Every known place is shared; the line names one of them.
    line = PLACE_LINES[rng.choice(me["places"])["kind"]] if kind == "share_place" else rng.choice(LINES[kind])
    return {"line": line.format(name=addressee["name"]), "act": act, "addressee": addressee["id"],
            "topic": scene["topic"]}


def _act(scene: Mapping[str, Any], me: Mapping[str, Any], rng: Random) -> tuple[str, str]:
    # Returns the act and which lines voice it.
    if not scene["turns"]:
        return "greet", "greet"
    needs = me["needs"]
    if max(needs["thirst"], needs["fatigue"], needs["bladder"]) >= PRESSING:
        return "leave_conversation", "pressed"
    said = {turn["act"] for turn in scene["turns"] if turn["speaker"] == me["id"]}
    # Even a guest with company enough answers once before taking their leave.
    if needs["social"] < CONTENT and said - {"greet"}:
        return "leave_conversation", "content"
    if "complain" not in said and rng.random() < _temper(me):
        return "complain", "complain"
    if "share_place" not in said and me["places"]:
        return "share_place", "share_place"
    friendly = "joke" if rng.random() < JOKES else "small_talk"
    return friendly, friendly


def _temper(me: Mapping[str, Any]) -> float:
    # Sober guests never grumble; each beer past the first makes an impatient one likelier to.
    patience = me["traits"].get("patience", 0.5)
    return min(1.0, 0.5 * max(0, me["visit"]["beers"] - 1) * (1 - patience))


async def write_scripted_turn(view: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    """Write a scripted line through the turn writer port (`turns.TurnWriter`), offline.

    Args:
        view: Scene view of `turns.turn_view`.
        config: AI config; unused, as no model is asked.

    Returns:
        The result of `scripted_turn`.
    """
    return scripted_turn(view)
