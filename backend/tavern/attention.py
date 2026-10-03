"""Attention: each tick's sounds draw a glance, or interrupt what a visitor can break off."""

from collections.abc import Mapping, Sequence
from typing import Any

from tavern.activities import ACTIVITIES
from tavern.expression import look_at, show_emote
from tavern.hearing import Stimulus, salience
from tavern.memory import record_event
from tavern.room import object_cells
from tavern.thoughts import friends_of


def attend(world: dict[str, Any]) -> list[dict[str, Any]]:
    """Let every visitor attend to the sounds made since the last tick, once each.

    Each visitor reacts only to the most salient sound (the earliest on a tie). Below the
    `attention.glance` rule they ignore it; below `attention.interrupt` they glance at it for
    `glance_seconds` unless already looking at something; above it they turn to it for `turn_seconds`, show an alert, and either
    break off an interruptible activity (or, when idle, drop a pending decision: see
    `interrupted_at`) or, busy with something they finish first, just remember hearing it.

    Args:
        world: World whose pending `stimuli` are consumed; visitors are updated in place and
            interrupts and alerts are logged.

    Returns:
        Visitors whose activity must stop; the world clears their actions.
    """
    stimuli, world["stimuli"] = world["stimuli"], []
    rules, stops = world["rules"]["attention"], []
    for actor in world["actors"]:
        friends = friends_of(actor)
        heard = [(salience(world, stimulus, actor, friends), stimulus) for stimulus in stimuli]
        level, stimulus = max(heard, key=lambda item: item[0], default=(0.0, None))
        if stimulus is None or level < rules["glance"]:
            continue
        if level < rules["interrupt"]:
            # A glance never pulls the eyes off something they are already looking at.
            if not actor["gaze"] or actor["gaze"]["until"] <= world["time"]:
                look_at(actor, stimulus["cell"], world["time"] + rules["glance_seconds"], stimulus["id"])
        elif _alert(world, actor, stimulus):
            stops.append(actor)
    return stops


def _alert(world: dict[str, Any], actor: dict[str, Any], stimulus: Stimulus) -> bool:
    now = world["time"]
    look_at(actor, stimulus["cell"], now + world["rules"]["attention"]["turn_seconds"], stimulus["id"])
    show_emote(actor, "alert", now + world["rules"]["emote_seconds"]["alert"])
    heard = f"{stimulus['noun']} {_landmark(world['map'], stimulus['cell'])}"
    action = actor["action"]
    if action and not ACTIVITIES[action["verb"]].interruptible:
        record_event(world, actor, "alerted", f"{actor['name']} heard {heard} while busy: {stimulus['cause']}")
        return False
    actor["interrupted_at"] = now
    turned = "broke off and turned" if action else "turned"
    record_event(world, actor, "interrupted", f"{actor['name']} {turned} toward {heard}: {stimulus['cause']}")
    return action is not None


def _landmark(world_map: Mapping[str, Any], cell: Sequence[int]) -> str:
    # Chairs are named after their tables, so the tables name the place; ties go to map order.
    places = [item for item in world_map["objects"] if item["kind"] != "chair"]
    if not places:
        return "in the hall"
    nearest = min(places, key=lambda item: min(abs(x - cell[0]) + abs(y - cell[1]) for x, y in object_cells(item)))
    return f"near the {nearest['name']}"
