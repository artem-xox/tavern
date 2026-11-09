"""The player's commands: check one and apply it to the world and the mind loop."""

from collections.abc import Mapping
from typing import Any

from tavern.body.activities import ACTIVITIES
from tavern.evening.mind_loop import MindLoop
from tavern.hall.memory import log_event
from tavern.hall.player import steered
from tavern.hall.state import Actor, World, find_actor
from tavern.body.items import ITEMS
from tavern.body.queues import cut_in, must_wait
from tavern.hall.world import observe_actor, start_action, start_refusal
from tavern.mind.candidates import Action, action, open_actions
from tavern.mind.scripted import MAX_LINE
from tavern.social.heckles import answer_heckle
from tavern.social.scenes import conversation_of
from tavern.social.speeches import on_stage_for
from tavern.social.stage_lines import comeback_owed_to


def steer(world: World, mind: MindLoop, command: Mapping[str, Any]) -> None:
    """Take the wheel of the played guest for the player, or give it back to the guest's own mind (autopilot).

    Taking it overrules a decision in flight, cancels an intention and an invitation answer in flight, and drops a
    claim on the guest's next line, so that nothing a model answers later reaches the guest. Giving it back lets
    the guest's mind decide and take stock again at once.

    Args:
        world: Authoritative world, whose `player` and event log are updated in place.
        mind: The evening's requests in flight.
        command: `{"type": "steer", "on": bool}`.

    Raises:
        ValueError: The evening has no player, or `on` is not true or false. Nothing changes then.
    """
    player = world["player"]
    if player is None:
        raise ValueError("steer needs a player, and this evening has none")
    on = command.get("on")
    if type(on) is not bool:
        raise ValueError(f"steer needs on to be true or false, not {on!r}")
    actor_id = player["actor_id"]
    player["steering"] = on
    if on:
        _drop_requests(world, mind, actor_id)
    else:
        mind.next_decision.pop(actor_id, None)
        mind.next_intention.pop(actor_id, None)
    people = [*world["actors"], *world["departed"], *world["expected"]]
    name = next(item["name"] for item in people if item["id"] == actor_id)
    log_event(world, actor_id, "steer", f"{name} is played by a person now" if on else f"{name} is on autopilot")


def _drop_requests(world: World, mind: MindLoop, actor_id: str) -> None:
    mind.overrule(actor_id)
    if actor_id in mind.pending:
        mind.courier.cancel(mind.pending.pop(actor_id)[0])
        mind.asked_at.pop(actor_id, None)
    if actor_id in mind.intending:
        mind.courier.cancel(mind.intending.pop(actor_id)[0])
    for scene in world["conversations"]:
        claim = scene["writing"]
        if claim is None or claim["speaker"] != actor_id or scene["written"] is not None:
            continue
        key = (scene["id"], claim["turn"])
        scene["writing"] = None
        if key in mind.writing:
            mind.courier.cancel(mind.writing.pop(key))
        if key in mind.answering:
            mind.courier.cancel(mind.answering.pop(key)[0])


def _played_guest(world: World, command: str) -> Actor:
    # The body the player holds the wheel of, or the reason they cannot use their hands now.
    player = world["player"]
    if player is None:
        raise ValueError(f"{command} needs a player, and this evening has none")
    if not steered(world, player["actor_id"]):
        raise ValueError(f"{command} needs the wheel, and the guest is on autopilot")
    guest = find_actor(world, player["actor_id"])
    if guest is None:
        raise ValueError(f"{command}: the played guest is not in the hall")
    return guest


def act(world: World, command: Mapping[str, Any]) -> None:
    """Start an action for the played guest, as a decision of their own would.

    The world checks it like any guest's (`start_action`), and the guest's `decision` says the player chose it.
    Leaving a scene for another action ends the guest's part in it by the scene's own rule.

    Args:
        world: Authoritative world, whose played guest and event log are updated in place.
        command: `{"type": "act", "action": {"id", "verb", "target_id"?, "item"?, "cell"?}}`.

    Raises:
        ValueError: The evening has no player, the guest is on autopilot or not in the hall, the command names no
            action, or the world refuses it (the world's reason). Nothing starts then.
    """
    guest = _played_guest(world, "act")
    action = command.get("action")
    if not isinstance(action, Mapping):
        raise ValueError(f"act needs an action, not {action!r}")
    result = start_action(world, guest["id"], action)
    if not result["accepted"]:
        raise ValueError(result["reason"])
    guest["decision"] = {"source": "player", "scores": {}, "error": None}
    log_event(world, guest["id"], "player_act", f"{guest['name']} chose {action['verb']}")["verb"] = action["verb"]


def options(world: World, command: Mapping[str, Any]) -> dict[str, Any]:
    """List the actions open to the played guest now, as their own mind would be offered them.

    The world stays as it is, apart from the knowledge refresh `observe_actor` does for every decision.

    Args:
        world: Current world.
        command: `{"type": "options", "target_id"?: str}`; with a target, only the actions aimed at it.

    Returns:
        `{"type": "options", "target_id": str | None, "options": [{"action": Action, "label": str}]}`, the label
        being the verb's own (`Activity.label`).

    Raises:
        ValueError: The evening has no player, the guest is on autopilot or not in the hall, or `target_id` is
            not a nonempty string.
    """
    guest = _played_guest(world, "options")
    target = command.get("target_id")
    if target is not None and (not isinstance(target, str) or not target):
        raise ValueError(f"options needs target_id to be a nonempty string, not {target!r}")
    aimed = _aimed_at(world, target)
    wanted = [item for item in open_actions(observe_actor(world, guest["id"]))
              if target is None or item["target_id"] in aimed]
    listed = list({item["id"]: item for item in [*wanted, *_body_actions(world, guest, aimed)]}.values())
    return {"type": "options", "target_id": target,
            "options": [{"action": item, "label": ACTIVITIES[item["verb"]].label or item["verb"].replace("_", " ")}
                        for item in listed]}


def _aimed_at(world: World, target: str | None) -> list[str | None]:
    # A click on a table means its own places too (its chairs): what stands at it carries its `table_id`.
    if target is None:
        return [None]
    return [target, *(item["id"] for item in world["map"]["objects"] if item.get("table_id") == target)]


def _body_actions(world: World, guest: Actor, targets: list[str | None]) -> list[Action]:
    # Every verb the body may start now at these targets (`start_refusal`), wanted by the guest's mind or not. Decision
    # steps, plans and floor walks are left to the mind's list and the floor click; an item-naming verb is tried with
    # each item in hand. A cut in line nobody waits in is the plain use of the place, already listed, so it is dropped.
    found: list[Action] = []
    for verb, activity in ACTIVITIES.items():
        if activity.duration is None or activity.opens_project or activity.to_cell or activity.staff_only:
            continue
        items = [kind for kind in ITEMS if guest["inventory"].get(kind)] if activity.names_item else [None]
        for target in targets:
            for item in items:
                candidate = action(verb, target, item)
                resolved = cut_in(world, candidate)[0]
                if start_refusal(world, guest["id"], candidate) is None and (
                        resolved["verb"] == verb or must_wait(world, guest, resolved)):
                    found.append(candidate)
    return found


def say(world: World, mind: MindLoop, command: Mapping[str, Any]) -> None:
    """Type a line to the scene the played guest is in: claim the scene's next slot and have the line read.

    The guests will hear the player's exact words; a model only reads which speech act they perform. A guest's
    line in flight for the slot, or already written but not spoken, is dropped (the guest is asked again after the
    player's line), so the player cuts in.

    Args:
        world: Authoritative world, whose scene gets the player's claim.
        mind: The evening's requests in flight.
        command: `{"type": "say", "text": str, "to": "auto" | "everyone" | <guest id>}`; `to` defaults to auto.

    Raises:
        ValueError: The evening has no player or the guest is on autopilot; the guest is in no scene and on no
            stage ("Nobody is listening"); the text,
            once trimmed, is empty or longer than `MAX_LINE`; `to` names nobody else in the scene; or a line of
            theirs is already being read or waits to be spoken there. Nothing changes then.
    """
    player = world["player"]
    if player is None or not player["steering"]:
        raise ValueError("say needs a player who holds the wheel")
    actor_id = player["actor_id"]
    text, to = command.get("text"), command.get("to", "auto")
    if not isinstance(text, str) or not text.strip() or len(text.strip()) > MAX_LINE:
        raise ValueError(f"say needs text of 1 to {MAX_LINE} characters, not {text!r}")
    if _say_on_stage(world, mind, actor_id, text.strip()):
        return
    scene = conversation_of(world, actor_id)
    if scene is None:
        raise ValueError("Nobody is listening: join a conversation or climb the stage to say anything")
    if to not in ("auto", "everyone") and (not isinstance(to, str) or to == actor_id
                                           or to not in scene["participants"]):
        raise ValueError(f"say needs to to be auto, everyone or someone else in the scene, not {to!r}")
    claim = scene["writing"]
    if claim is not None and claim["speaker"] == actor_id:
        raise ValueError("A line of the player's is being read or waits to be spoken: one at a time")
    if claim is not None:
        _drop_claim(mind, scene["id"], claim["turn"])
    scene["written"] = None
    scene["writing"] = {"turn": len(scene["turns"]), "speaker": actor_id, "since": world["time"]}
    mind.read_line(world, scene["id"], text.strip(), to)


def _say_on_stage(world: World, mind: MindLoop, actor_id: str, text: str) -> bool:
    # A heckle owed a comeback takes the text as the comeback at once; a performer with no number given takes it as
    # their number, after a reading. Returns False when the played guest is on neither errand: the scene's path.
    performer = find_actor(world, actor_id)
    if performer is None:
        return False
    heckler = comeback_owed_to(world, actor_id)
    if heckler is not None:
        answer_heckle(world, performer, heckler, text)
        return True
    if on_stage_for(world, performer) is None:
        return False
    if actor_id in mind.numbering:
        raise ValueError("A number of the player's is being read: one at a time")
    mind.read_number(world, text)
    return True


def _drop_claim(mind: MindLoop, scene_id: str, turn: int) -> None:
    # The guest's request for this slot, a line or an invitation answer, is cancelled: nothing it answers is wanted.
    key = (scene_id, turn)
    if key in mind.writing:
        mind.courier.cancel(mind.writing.pop(key))
    if key in mind.answering:
        mind.courier.cancel(mind.answering.pop(key)[0])


def typing(world: World, command: Mapping[str, Any]) -> None:
    """Note that the player just pressed a key, so their scene waits for them (`turns.speak_turns`).

    Not logged: the client sends one at most every 2 s.

    Args:
        world: Authoritative world, whose player record is updated in place.
        command: `{"type": "typing"}`.

    Raises:
        ValueError: The evening has no player, or the guest is on autopilot.
    """
    player = world["player"]
    if player is None or not player["steering"]:
        raise ValueError("typing needs a player who holds the wheel")
    player["typing_at"] = world["time"]


PLAYER_COMMANDS = ("steer", "act", "say", "options", "typing")


def apply_command(world: World, mind: MindLoop, command: Mapping[str, Any]) -> dict[str, Any] | None:
    """Route one player command to its handler: the one door the live runtime and a scripted evening share.

    Args:
        world: Authoritative world.
        mind: The evening's requests in flight.
        command: A `steer`, `act`, `say`, `options` or `typing` command.

    Returns:
        The reply to send back (`options` has one), or None.

    Raises:
        ValueError: The type is not a player command, or the handler refuses the command.
    """
    kind = command.get("type")
    if kind == "steer":
        steer(world, mind, command)
    elif kind == "act":
        act(world, command)
    elif kind == "say":
        say(world, mind, command)
    elif kind == "options":
        return options(world, command)
    elif kind == "typing":
        typing(world, command)
    else:
        raise ValueError(f"Unknown player command {kind!r}; choose one of {PLAYER_COMMANDS}")
    return None
