"""Commitments: a promise made in talk, and whether the world shows it kept.

A `promise` act leaves a `Commitment` in `world["commitments"]`: one guest will do a kind of `goals.GOALS` for
another by a game time. It is the same kind of aim a goal names, so what serves a goal serves a promise, and the
world, not the words, says whether it was kept: `settle_commitments` ends each commitment once, as kept or
broken, and the one it was made to keeps a thought about the promiser either way.
"""

from collections.abc import Mapping
from typing import Any, TypedDict

from tavern.hall.memory import log_event, record_event
from tavern.hall.state import Actor, World, find_actor
from tavern.hall.validation import number
from tavern.mind.goals import GOALS, Goal
from tavern.social.names import called
from tavern.social.scenes import Conversation
from tavern.social.thoughts import think

# What a promise is for, and how long a guest has to keep it: a promise to come over is not an invitation (the
# world sets nothing in motion), so the guest, deciding for themselves, has this long to do it.
PROMISE_KIND = "sit_with"
PROMISE_LASTS = 90.0

# `from` is a Python keyword, hence the functional form.
Commitment = TypedDict("Commitment", {"kind": str, "from": str, "to": str, "made_at": float, "by": float})


def promise(world: World, scene: Conversation, speaker: Actor, addressee: Actor | None) -> None:
    """Let a speaker promise the addressee to come and sit with them.

    Args:
        world: World whose `commitments` and the addressee's thoughts are updated in place.
        scene: Speaker's scene.
        speaker: Visitor promising.
        addressee: Visitor promised to.

    Raises:
        ValueError: Nobody in particular was addressed: a promise is made to someone.
    """
    if addressee is None:
        raise ValueError("A promise is made to someone in particular")
    now = world["time"]
    world["commitments"].append({"kind": PROMISE_KIND, "from": speaker["id"], "to": addressee["id"],
                                 "made_at": now, "by": now + PROMISE_LASTS})
    message = f"{speaker['name']} promised {addressee['name']} to come and sit with them"
    log_event(world, speaker["id"], "promise_made", message)
    think(addressee, "promised", now, f"{called(addressee, speaker)} promised to come and sit with me", message,
          about=speaker)


def promisable(world: Mapping[str, Any], speaker: Mapping[str, Any], other: Mapping[str, Any]) -> bool:
    """Tell whether a speaker may promise someone to come and sit with them.

    Args:
        world: Current world.
        speaker: Visitor who would promise.
        other: Visitor they would promise.

    Returns:
        True when the other has a table (the one they sit at, or else the one whose chair is their own), the speaker
        does not sit at that same table, and the speaker has no open promise to them.
    """
    chairs = {item["id"]: item.get("table_id") for item in world["map"]["objects"] if item["kind"] == "chair"}
    table = chairs.get(other.get("seat_id") or other.get("favorite_seat_id"))
    return (table is not None and chairs.get(speaker.get("seat_id")) != table
            and not any(item["from"] == speaker["id"] and item["to"] == other["id"] for item in world["commitments"]))


def promises_of(world: Mapping[str, Any], actor_id: str) -> list[Goal]:
    """List what a guest has promised and not yet kept, as goals.

    Args:
        world: Current world.
        actor_id: Guest.

    Returns:
        An active goal for each open commitment made by the guest, in the order they were made.
    """
    return [Goal(kind=item["kind"], target=item["to"], status="active")
            for item in world["commitments"] if item["from"] == actor_id]


def settle_commitments(world: World) -> None:
    """End the commitments the world has decided, once each, and log how.

    Args:
        world: World whose `commitments`, events and thoughts are updated in place. A commitment is kept once its
            kind's `reached` holds, broken once it falls due or its promiser has left; it is void, with nothing
            logged but `promise_void`, once the one it was made to has left.
    """
    for item in list(world["commitments"]):
        promiser, other = find_actor(world, item["from"]), find_actor(world, item["to"])
        if other is None:
            _end(world, item, None, "promise_void", None)
        elif promiser is not None and GOALS[item["kind"]].reached(world, promiser, other, item["made_at"]):
            _end(world, item, promiser, "promise_kept", other)
        elif promiser is None or world["time"] >= item["by"]:
            _end(world, item, promiser, "promise_broken", other)


def _end(world: World, item: Commitment, promiser: Actor | None, kind: str, other: Actor | None) -> None:
    world["commitments"].remove(item)
    names = {actor["id"]: actor["name"] for actor in [*world["actors"], *world["departed"]]}
    message = f"{names[item['from']]}'s promise to {names[item['to']]}: {kind.removeprefix('promise_')}"
    if promiser is None or other is None:
        log_event(world, item["from"], kind, message)
    else:
        record_event(world, promiser, kind, message)
    if other is not None and kind != "promise_void":
        speaker = next(actor for actor in [*world["actors"], *world["departed"]] if actor["id"] == item["from"])
        thought = "kept_word" if kind == "promise_kept" else "let_down"
        words = "kept their word" if thought == "kept_word" else "broke their word"
        think(other, thought, world["time"], f"{called(other, speaker)} {words} to me", message, about=speaker)


def check_commitments(world: Mapping[str, Any]) -> None:
    """Check a saved world's commitments.

    Args:
        world: Untrusted saved world with `commitments`.

    Raises:
        ValueError: `commitments` is not a list, or one is not exactly a kind of `GOALS`, two different guests of
            the evening, and a time made and a later time due.
    """
    items, guests = world.get("commitments"), [item["id"] for item in [*world["actors"], *world["departed"]]]
    if not isinstance(items, list):
        raise ValueError("Saved commitments must be a list")
    for item in items:
        if (not isinstance(item, dict) or set(item) != {"kind", "from", "to", "made_at", "by"}
                or item["kind"] not in GOALS or item["from"] not in guests or item["to"] not in guests
                or item["from"] == item["to"]):
            raise ValueError(f"Invalid saved commitment {item!r}")
        if not number(item["made_at"], "Commitment time", 0, float("inf")) < number(
                item["by"], "Commitment deadline", 0, float("inf")):
            raise ValueError(f"A commitment falls due after it was made, not {item!r}")
