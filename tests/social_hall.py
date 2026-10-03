"""A small hall for speech-act, invitation, overhearing and name tests (helpers, not tests)."""

from typing import Any

from tavern.cards import PARAMS
from tavern.scenes import conversation_of
from tavern.turns import claim_turns, deliver_turn
from tavern.world import create_world, start_action, step_world

LOOKS = {"ada": "the tall woman in a red shawl", "bea": "the stout woman with a pipe",
         "cid": "the grey-bearded man in a green cloak", "dan": "the lanky lad with a lute"}


def chair(chair_id: str, x: int, y: int, table: str) -> dict[str, Any]:
    """Build a walkable chair at a table."""
    return {"id": chair_id, "kind": "chair", "name": f"{table.title()} table · {chair_id}", "x": x, "y": y,
            "walkable": True, "table_id": table, "interaction_spots": [[x, y]]}


def card(guest_id: str) -> dict[str, Any]:
    """Build a complete character card for a guest, with their looks."""
    words = dict.fromkeys(("occupation", "background", "temperament", "speech", "quirks", "secret", "goal"),
                          "Something.")
    return {"id": guest_id, "name": guest_id.title(), "sprite": "visitor", "looks": LOOKS[guest_id], **words,
            "params": dict.fromkeys(PARAMS, 0.5)}


def hall(cards: bool = False, wall: bool = False) -> dict[str, Any]:
    """Build a 12×8 hall: a near and a far table three cells apart, a tap, darts, a fire and a door.

    Ada and Bea stand by the near table, Cid by the far one, Dan by the fire. With `cards`, every
    guest is cast from a card with looks; with `wall`, a thick wall runs between the two tables.
    """
    guests = [{"id": "ada", "x": 2, "y": 2}, {"id": "bea", "x": 5, "y": 2}, {"id": "cid", "x": 2, "y": 5},
              {"id": "dan", "x": 9, "y": 6}]
    for item in guests:
        item.update(name=item["id"].title(), **({"card": card(item["id"])} if cards else {}))
    return {"width": 12, "height": 8, "blocked": [[x, y] for x in range(0, 8) for y in (3, 4)] if wall else [], "objects": [
        {"id": "near", "kind": "table", "name": "Near table", "x": 3, "y": 2, "width": 2, "height": 1},
        chair("w", 2, 2, "near"), chair("e", 5, 2, "near"), chair("n", 3, 1, "near"),
        {"id": "far", "kind": "table", "name": "Far table", "x": 3, "y": 5, "width": 2, "height": 1},
        chair("fw", 2, 5, "far"), chair("fe", 5, 5, "far"),
        {"id": "tap", "kind": "tap", "name": "Tap", "x": 11, "y": 0, "interaction_spots": [[10, 0]], "stock": 9},
        {"id": "darts", "kind": "darts", "name": "Darts", "x": 11, "y": 3, "interaction_spots": [[10, 3]],
         "queue_spots": [[10, 4], [10, 5]]},
        {"id": "fire", "kind": "fireplace", "name": "Fire", "x": 9, "y": 7, "interaction_spots": [[9, 6]],
         "appeal": 0.5, "reach": 3},
        {"id": "door", "kind": "door", "name": "Door", "x": 0, "y": 7, "interaction_spots": [[0, 6]]},
    ], "actors": guests}


def command(verb: str, target: str | None = None) -> dict[str, Any]:
    """Build an executable action."""
    return {"id": verb if target is None else f"{verb}:{target}", "verb": verb, "target_id": target}


def advance(world: dict[str, Any], seconds: float) -> None:
    """Advance the world in 0.1 s ticks, without anyone deciding."""
    for _ in range(round(seconds * 10)):
        step_world(world, 0.1)


def actor(world: dict[str, Any], actor_id: str) -> dict[str, Any]:
    """Find a guest in the hall or among the departed."""
    return next(item for item in [*world["actors"], *world["departed"]] if item["id"] == actor_id)


def know(world: dict[str, Any], actor_id: str, *object_ids: str) -> None:
    """Let a guest know where places are."""
    objects = {item["id"]: item for item in world["map"]["objects"]}
    for object_id in object_ids:
        actor(world, actor_id)["knowledge"]["objects"][object_id] = {**objects[object_id], "last_seen": 0.0}


def seated_talk(cards: bool = False, wall: bool = False, social: float = 95.0, cid_joins: bool = False,
                seed: int = 4) -> dict[str, Any]:
    """Seat Ada and Bea at the near table, Cid at the far one, and let Ada start talking to Bea."""
    world = create_world(hall(cards, wall), seed)
    for actor_id, seat in (("ada", "w"), ("bea", "e"), ("cid", "fw")):
        assert start_action(world, actor_id, command("sit", seat))["accepted"]
    if cid_joins:
        assert start_action(world, "cid", command("sit", "n"))["accepted"]
        advance(world, 3)
    for item in world["actors"]:
        item["needs"]["social"] = social
    assert start_action(world, "ada", command("talk", "bea"))["accepted"]
    if cid_joins:
        assert start_action(world, "cid", command("join_conversation", "ada"))["accepted"]
    return world


def by_the_fire() -> dict[str, Any]:
    """Ada and Dan stand by the fire talking; Ada's own seat is at the near table, Bea sits at it."""
    data = hall()
    data["actors"][0].update(x=9, y=5)
    world = create_world(data, 4)
    assert start_action(world, "bea", command("sit", "e"))["accepted"]
    advance(world, 1)
    for item in world["actors"]:
        item["needs"]["social"] = 95.0
    actor(world, "ada")["favorite_seat_id"] = "w"
    assert start_action(world, "ada", command("talk", "dan"))["accepted"]
    return world


def say(world: dict[str, Any], act: str, line: str = "Well now.", addressee: str | None = "other",
        invitation: str | None = None) -> str:
    """Let whoever speaks next in Ada's scene say a line with an act, and speak it.

    Args:
        world: World with a scene Ada takes part in.
        act: Speech act.
        line: Words.
        addressee: Whom it addresses; "other" means the participant after the speaker, None everyone.
        invitation: Invitation kind of an `invite`.

    Returns:
        The speaker's ID.
    """
    scene = next(item for item in world["conversations"] if "ada" in item["participants"]
                 or any(turn["speaker"] == "ada" for turn in item["turns"]))
    [(scene_id, turn, view)] = [claim for claim in claim_turns(world) if claim[0] == scene["id"]]
    speaker, people = view["speaker"]["id"], scene["participants"]
    target = people[(people.index(speaker) + 1) % len(people)] if addressee == "other" else addressee
    result = {"line": line, "act": act, "addressee": target, "topic": "the road"}
    if invitation is not None:
        result["invitation"] = invitation
    deliver_turn(world, scene_id, turn, lambda: result)
    for _ in range(100):
        if len(scene["turns"]) > turn:
            # A rejected line falls back to a scripted one; a test must notice.
            assert scene["turns"][turn]["act"] == act, [e["message"] for e in world["events"][-5:]]
            return speaker
        step_world(world, 0.1)
    raise AssertionError(f"The line was never spoken: {[e['message'] for e in world['events'][-5:]]}")


def scene_of(world: dict[str, Any], actor_id: str = "ada") -> dict[str, Any] | None:
    """Find the scene a guest takes part in."""
    return conversation_of(world, actor_id)
