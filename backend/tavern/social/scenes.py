"""Conversation scenes: who talks together, who may join, and when someone leaves or the scene ends.

A scene lives in `world["conversations"]`. It is held at a table (`table_id`) by seated tablemates, or
standing (`table_id` None) by guests side by side in a line or by a view. Members keep their own
actions: whoever started or joined it holds `talk` or `join_conversation`, which the scene, not a
timer, ends. When the next turn is spoken is `tavern.social.turns`' business; what an act does is
`tavern.social.conversation`'s.
"""

from collections.abc import Collection, Mapping
import math
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

from tavern.hall.closing import inn_closed
from tavern.hall.memory import record_event
from tavern.hall.room import find_object
from tavern.hall.state import Actor, World
from tavern.hall.validation import number

if TYPE_CHECKING:  # turns imports this module, so the type crosses the cycle only for the checker.
    from tavern.social.turns import TurnResult


class Turn(TypedDict):
    """One spoken line: who said it, to whom (None for everyone), the speech act, and the game time.

    An `invite` also names the `invitation` kind (see `tavern.social.invitations`).
    """

    speaker: str
    addressee: str | None
    line: str
    act: str
    time: float
    invitation: NotRequired[str]


class Claim(TypedDict):
    """A turn a runner is writing: its index in the scene, its speaker, and since when (game seconds)."""

    turn: int
    speaker: str
    since: float


class Conversation(TypedDict):
    """A conversation scene.

    `participants` are in order of joining (the starter first). `next_turn_at` is when the next line
    is due. `writing` is the turn a runner's writer is working on, if any, and `written` its
    answer (`turns.TurnResult`) waiting for `next_turn_at`. `invitation` is the one waiting
    for an answer (`invitations.Invitation`, from and to members), if any; it lapses when either
    leaves.
    """

    id: str
    participants: list[str]
    table_id: str | None
    topic: str
    turns: list[Turn]
    started_at: float
    next_turn_at: float
    writing: Claim | None
    written: "TurnResult | None"
    invitation: dict[str, str] | None


# What a new scene is about, by how many conversations the starter remembers.
TOPICS = ("stories from the road", "the inn's beer", "their next journey", "a game of darts")


def conversation_of(world: Mapping[str, Any], actor_id: Any) -> Conversation | None:
    """Find the scene a visitor takes part in.

    Args:
        world: Current world.
        actor_id: Visitor looked for.

    Returns:
        Their scene, or None when they are in no conversation.
    """
    return next((scene for scene in world["conversations"] if actor_id in scene["participants"]), None)


def table_of(world: Mapping[str, Any], actor: Mapping[str, Any]) -> str | None:
    """Tell at which table a visitor sits.

    Args:
        world: Current world.
        actor: Visitor.

    Returns:
        The table ID of their seat, or None when they are not seated at a table.
    """
    seat = find_object(world["map"], actor.get("seat_id"))
    return seat.get("table_id") if seat else None


def pressed(world: Mapping[str, Any], actor: Mapping[str, Any]) -> bool:
    """Tell whether a need presses on a visitor too hard for a new conversation.

    Args:
        world: Current world; `rules.conversation.pressing` is the level that presses.
        actor: Visitor.

    Returns:
        True when their thirst, tiredness or bladder has reached that level: they decline to
        talk, and others can see they are in a hurry.
    """
    limit = world["rules"]["conversation"]["pressing"]
    return max(actor["needs"][need] for need in ("thirst", "fatigue", "bladder")) >= limit


def _lines(world: Mapping[str, Any]) -> dict[str, tuple[str, int]]:
    # The place and position of everyone standing in a line (see `tavern.body.queues`).
    return {entry["actor_id"]: (item["id"], place) for item in world["map"]["objects"]
            for place, entry in enumerate(item.get("queue", []))}


def _by_a_view(world: Mapping[str, Any], actor: Mapping[str, Any]) -> bool:
    # Standing at, or right beside, the spot from which the fire or a window is watched.
    return any(max(abs(actor["x"] - x), abs(actor["y"] - y)) <= 1 for item in world["map"]["objects"]
               if item["kind"] in ("fireplace", "window") for x, y in item["interaction_spots"])


def side_by_side(world: Mapping[str, Any], actor: Mapping[str, Any], other: Mapping[str, Any]) -> bool:
    """Tell whether two standing visitors are close enough to talk.

    Args:
        world: Current world; `rules.conversation.reach` is how many cells apart they may stand.
        actor: One visitor.
        other: The other visitor.

    Returns:
        True when neither sits, and they stand next to each other in the same line, or neither
        walks and both stand by the fire or a window within reach of each other.
    """
    if actor["id"] == other["id"] or actor.get("seat_id") or other.get("seat_id"):
        return False
    lines = _lines(world)
    mine, theirs = lines.get(actor["id"]), lines.get(other["id"])
    if mine and theirs:
        # Moving up one spot together keeps them side by side.
        return mine[0] == theirs[0] and abs(mine[1] - theirs[1]) == 1
    if "walking" in (actor["status"], other["status"]):
        return False
    near = max(abs(actor["x"] - other["x"]), abs(actor["y"] - other["y"])) <= world["rules"]["conversation"]["reach"]
    return near and _by_a_view(world, actor) and _by_a_view(world, other)


def start_conversation(world: World, actor: Actor, partner: Mapping[str, Any]) -> Conversation:
    """Open a scene between a visitor and a partner free to talk.

    Args:
        world: World whose `conversations` receive it and whose `next_conversation_id` numbers it.
        actor: Visitor starting it, validated by `tavern.body.actions`.
        partner: Visitor they talk to.

    Returns:
        The new scene; its first line is due `rules.conversation.opening` seconds from now.
    """
    count = sum(item["type"] == "conversation" for item in actor["memory"])
    scene: Conversation = {
        "id": f"conversation-{world['next_conversation_id']}", "participants": [actor["id"], partner["id"]],
        "table_id": table_of(world, actor), "topic": TOPICS[count % len(TOPICS)], "turns": [],
        "started_at": world["time"], "next_turn_at": world["time"] + world["rules"]["conversation"]["opening"],
        "writing": None, "written": None, "invitation": None}
    world["next_conversation_id"] += 1
    world["conversations"].append(scene)
    record_event(world, actor, "conversation_started", f"{actor['name']} started talking to {partner['name']}")
    return scene


def join_conversation(world: World, actor: Actor, member: Mapping[str, Any]) -> None:
    """Add a visitor to the scene of someone already talking.

    Args:
        world: Current world.
        actor: Visitor joining, validated by `tavern.body.actions`.
        member: Visitor in the scene they join.
    """
    scene = conversation_of(world, member["id"])
    if scene is None:
        raise ValueError(f"{member['name']} is in no conversation to join")
    names = _names(world, scene["participants"])
    _recast(scene)
    scene["participants"].append(actor["id"])
    record_event(world, actor, "joined_conversation", f"{actor['name']} joined {names}'s conversation")


def leave_conversation(world: World, actor: Actor) -> bool:
    """Take a visitor out of their scene; the others carry on while at least two remain.

    Args:
        world: World whose event log records it.
        actor: Visitor leaving.

    Returns:
        Whether they were in a scene.
    """
    scene = conversation_of(world, actor["id"])
    if scene is None:
        return False
    _recast(scene)
    scene["participants"].remove(actor["id"])
    _lapse(scene)
    record_event(world, actor, "left_conversation", f"{actor['name']} left the conversation")
    if len(scene["participants"]) < 2:
        end_conversation(world, scene, pleasant=True)
    return True


def end_conversation(world: World, scene: Conversation, pleasant: bool) -> None:
    """End a scene. One that ended pleasantly after an exchange is remembered by everyone still in it.

    Args:
        world: World whose `conversations` lose it.
        scene: Scene to end.
        pleasant: False when it broke up in a quarrel, which is remembered instead.
    """
    world["conversations"].remove(scene)
    # A greeting nobody answered is no conversation.
    if not pleasant or len(scene["turns"]) < 2:
        return
    members = [item for item in world["actors"] if item["id"] in scene["participants"]]
    message = f"{_names(world, scene['participants'])} chatted about {scene['topic']}"
    for member in members:
        record_event(world, member, "conversation", message)


def check_conversations(world: World) -> None:
    """Let scenes lose members who went away and end those that are over.

    A member leaves once gone home, no longer seated at the scene's table, or, standing, no longer
    beside anyone in it. Every scene ends at closing time, and, once its members have exchanged
    a line or two, when all their wish for company has dropped below `rules.conversation.satisfied`.

    Args:
        world: World whose scenes are updated in place.
    """
    for scene in list(world["conversations"]):
        if inn_closed(world):
            end_conversation(world, scene, pleasant=True)
            continue
        for actor in [item for item in world["actors"] if item["id"] in scene["participants"]]:
            if scene in world["conversations"] and not _still_there(world, scene, actor):
                leave_conversation(world, actor)
        _drop_departed(world, scene)
        members = [item for item in world["actors"] if item["id"] in scene["participants"]]
        if scene in world["conversations"] and len(scene["turns"]) >= 2 and all(
                item["needs"]["social"] < world["rules"]["conversation"]["satisfied"] for item in members):
            end_conversation(world, scene, pleasant=True)


def _drop_departed(world: World, scene: Conversation) -> None:
    # Someone who went home leaves no member record behind to log their leaving with.
    present = {item["id"] for item in world["actors"]}
    if scene not in world["conversations"] or set(scene["participants"]) <= present:
        return
    _recast(scene)
    scene["participants"] = [actor_id for actor_id in scene["participants"] if actor_id in present]
    _lapse(scene)
    if len(scene["participants"]) < 2:
        end_conversation(world, scene, pleasant=True)


def _still_there(world: Mapping[str, Any], scene: Conversation, actor: Mapping[str, Any]) -> bool:
    if scene["table_id"] is not None:
        return table_of(world, actor) == scene["table_id"]
    people = {item["id"]: item for item in world["actors"]}
    return any(side_by_side(world, actor, people[other]) for other in scene["participants"]
               if other != actor["id"] and other in people)


def _lapse(scene: Conversation) -> None:
    # An invitation nobody is left to make or answer is void.
    invitation = scene["invitation"]
    if invitation is not None and not {invitation["from"], invitation["to"]} <= set(scene["participants"]):
        scene["invitation"] = None


def _recast(scene: Conversation) -> None:
    # A line written for the old company no longer fits the new one.
    scene.update({"writing": None, "written": None})


def _names(world: Mapping[str, Any], actor_ids: list[str]) -> str:
    people = {item["id"]: item["name"] for item in world["actors"]}
    names = [people[actor_id] for actor_id in actor_ids if actor_id in people]
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def check_saved_scenes(world: Mapping[str, Any], invitation_kinds: Collection[str]) -> None:
    """Check the conversation scenes in a saved world.

    Args:
        world: Decoded save.
        invitation_kinds: Kinds an `invite` turn or written turn may name (`invitations.KINDS`); a
            parameter because `invitations` imports this module.
    Raises:
        ValueError: A scene, turn, claim or written turn is malformed, or a guest is in two scenes.
    """
    scenes, issued = world.get("conversations"), world.get("next_conversation_id")
    if type(issued) is not int or issued < 0 or not isinstance(scenes, list):
        raise ValueError("Invalid saved conversations")
    keys = {"id", "participants", "table_id", "topic", "turns", "started_at", "next_turn_at", "writing", "written",
            "invitation"}
    taken: list[Any] = []
    for scene in scenes:
        if not isinstance(scene, dict) or set(scene) != keys or not isinstance(scene["id"], str):
            raise ValueError("Invalid saved conversation")
        _validate_scene(scene, world, invitation_kinds)
        taken.extend(scene["participants"])
    if len(set(taken)) != len(taken) or len({scene["id"] for scene in scenes}) != len(scenes):
        raise ValueError("Saved guests may take part in one conversation at a time")


def _validate_scene(scene: Mapping[str, Any], world: Mapping[str, Any], invitation_kinds: Collection[str]) -> None:
    people, tables = {actor["id"] for actor in world["actors"]}, {
        item["id"] for item in world["map"]["objects"] if item["kind"] == "table"}
    members = scene["participants"]
    if not isinstance(members, list) or len(members) < 2 or len(set(members)) != len(members) or not set(
            members) <= people:
        raise ValueError("Saved conversation needs two or more distinct guests")
    if scene["table_id"] is not None and scene["table_id"] not in tables:
        raise ValueError("Saved conversation is held at an unknown table")
    if not isinstance(scene["topic"], str) or not isinstance(scene["turns"], list):
        raise ValueError("Invalid saved conversation topic or turns")
    number(scene["started_at"], "Saved conversation start", 0, world["time"])
    number(scene["next_turn_at"], "Saved next turn", 0, math.inf)
    for turn in scene["turns"]:
        # An invite also names its invitation kind.
        if not isinstance(turn, dict) or set(turn) - {"invitation"} != {"speaker", "addressee", "line", "act", "time"} \
                or ("invitation" in turn and turn["invitation"] not in invitation_kinds) or not all(
                isinstance(turn[key], str) for key in ("speaker", "line", "act")):
            raise ValueError("Invalid saved turn")
        number(turn["time"], "Saved turn time", 0, world["time"])
    claim = scene["writing"]
    if claim is not None and (not isinstance(claim, dict) or set(claim) != {"turn", "speaker", "since"}
                              or type(claim["turn"]) is not int or not isinstance(claim["speaker"], str)):
        raise ValueError("Invalid saved turn being written")
    written = scene["written"]
    if written is not None and (not isinstance(written, dict) or set(written) - {"invitation"} != {
            "line", "act", "addressee", "topic"} or ("invitation" in written and written["invitation"] not in invitation_kinds)):
        raise ValueError("Invalid saved written turn")
