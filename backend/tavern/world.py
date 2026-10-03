"""Serializable authoritative tavern state and physical action execution."""

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from tavern.actions import action_error
from tavern.activities import ACTIVITIES
from tavern.arrival import admit_arrivals, arrival_ranges, arriving, create_actor
from tavern.attention import attend
from tavern.closing import call_closing, inn_closed
from tavern.dozing import nodding_off
from tavern.drunkenness import wear_off
from tavern.expression import update_expression
from tavern.invitations import honor_invitations, invitations_of
from tavern.lifecycle import (activate, clear_action, finish_parts, line_up, look, notice_target, reject,
                              step_actor, talk_in_line)
from tavern.memory import record_event
from tavern.queues import check_lines, cut_in, line_of, must_wait
from tavern.room import create_map
from tavern.routes import plan_route
from tavern.rules import default_rules
from tavern.scenes import check_conversations
from tavern.sight import look_around, people_in_sight, visible_cells
from tavern.state import World, find_actor
from tavern.thoughts import forget_expired
from tavern.turns import speak_turns
from tavern.validation import number, unique_ids


def create_world(map_data: Mapping[str, Any], seed: int = 0) -> World:
    """Create and validate an independently owned, serializable room snapshot.

    Args:
        map_data: Flat room definition with geometry, objects, and initial actors. An optional
            `arrival` section maps needs to [low, high] ranges: visitors then arrive with needs
            drawn from them and look around the hall as they come in.
        seed: Saved deterministic seed of the evening's arrivals and decision policy.

    Returns:
        New world state containing no references to the supplied room definition. Nobody
        else is expected and the inn never closes; `scenario.open_evening` sets both.

    Raises:
        ValueError: Layout, IDs, resources, arrival ranges, or actor values are invalid.
    """
    world_map = create_map(map_data)
    unique_ids(map_data.get("actors", []), "actor")
    ranges, listed = arrival_ranges(map_data), map_data.get("actors", [])
    actors = [create_actor(item, world_map)
              for item in (listed if ranges is None else arriving(listed, ranges, seed))]
    if len({(item["x"], item["y"]) for item in actors}) != len(actors):
        raise ValueError("Actors cannot overlap at startup")
    world = World(schema_version=5, seed=seed, tick=0, time=0.0, paused=False, speed=1.0,
                  map=world_map, actors=actors, departed=[], expected=[], closes_at=None,
                  events=[], stimuli=[], next_stimulus_id=0, conversations=[], next_conversation_id=0,
                  invitations=[], rules=default_rules())
    check_lines(world)
    for actor in actors:
        look(world, actor)
        if ranges is not None:
            look_around(world, actor)
    return world


def start_action(world: World, actor_id: str, action: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and start a physical action, replacing any current valid action.

    Args:
        world: Authoritative mutable world state.
        actor_id: Visitor to control.
        action: Nonempty ID, supported verb, and optional target ID.

    Returns:
        Acceptance flag and a human-readable refusal reason, or None on success.

    Raises:
        ValueError: Not raised for rejected commands; refusals are returned.
    """
    actor = find_actor(world, actor_id)
    if actor is None:
        return {"accepted": False, "reason": "Unknown visitor"}
    cutting = action.get("verb") == "cut_in_line"
    action, reason = cut_in(world, action)
    reason = reason or action_error(world, actor, action)
    if reason:
        notice_target(world, actor, action)
        return reject(world, actor, reason)
    if ACTIVITIES[action["verb"]].partner and line_of(world, actor_id) is not None:
        return talk_in_line(world, actor, action)
    if must_wait(world, actor, action):
        return line_up(world, actor, action, cutting)
    plan = plan_route(world, actor, action)
    if plan is None:
        return reject(world, actor, "No reachable interaction spot")
    activate(world, actor, action, plan)
    return {"accepted": True, "reason": None}


def step_world(world: World, dt: float) -> None:
    """Advance time, needs, movement, once-only action consequences, arrivals, and attention.

    Args:
        world: Authoritative mutable world state.
        dt: Unscaled elapsed seconds; world speed is applied inside this function.

    Returns:
        None. Mutates the supplied world in place.

    Raises:
        ValueError: Delta time or speed is invalid.
    """
    elapsed = number(dt, "Delta time", 0, float("inf"))
    if world["paused"] or elapsed == 0:
        return
    elapsed *= number(world["speed"], "Speed", 0.01, 100)
    since = world["time"]
    world["time"] += elapsed
    world["tick"] += 1
    forget_expired(world)
    for actor in world["actors"]:
        step_actor(world, actor, elapsed)
    _see_off(world)
    call_closing(world, since)
    admit_arrivals(world)
    check_conversations(world)
    speak_turns(world)
    honor_invitations(world, start_action)
    for actor in attend(world):
        clear_action(world, actor)
    wear_off(world, elapsed)
    for actor in nodding_off(world, elapsed):
        activate(world, actor, {"id": "doze", "verb": "doze", "target_id": None}, (None, []))
    finish_parts(world)
    update_expression(world)


def _see_off(world: World) -> None:
    # Visitors who stepped out keep their record, so the evening stays inspectable.
    for actor in [item for item in world["actors"] if "left_at" in item["visit"]]:
        world["actors"].remove(actor)
        world["departed"].append(actor)
        beers = actor["visit"]["beers"]
        record_event(world, actor, "departure",
                f"{actor['name']} left the inn after {beers} {'beer' if beers == 1 else 'beers'}")


def observe_actor(world: Mapping[str, Any], actor_id: str) -> dict[str, Any]:
    """Refresh and return a visitor's personal observation without private leaks.

    Args:
        world: World whose actor knowledge is refreshed in place.
        actor_id: Visitor making the observation.

    Returns:
        Own actor state, known object records, personal memories, map bounds, visible
        cells, and whether the inn has closed. Unseen resource changes remain remembered
        historical values.

    Raises:
        ValueError: Visitor ID does not exist.
    """
    actor = find_actor(world, actor_id)
    if actor is None:
        raise ValueError("Unknown visitor")
    visible = look(world, actor)
    return {"actor": deepcopy(actor), "objects": deepcopy(list(actor["knowledge"]["objects"].values())),
            "visitors": _visible_visitors(world, actor),
            "memory": deepcopy(actor["memory"][-10:]), "visible_cells": visible, "time": world["time"],
            "invitations": invitations_of(world, actor),
            "map": {"width": world["map"]["width"], "height": world["map"]["height"]},
            "closed": inn_closed(world)}


def _visible_visitors(world: Mapping[str, Any], actor: Mapping[str, Any]) -> list[dict[str, Any]]:
    # Only seated company is actionable in this small social demo.
    return [person for person in people_in_sight(world, actor) if person["seat_id"]]


def observe_people(world: Mapping[str, Any], actor_id: str) -> list[dict[str, Any]]:
    """List everyone a visitor can see and what they are visibly doing.

    Args:
        world: Current world; it is not modified.
        actor_id: Visitor doing the looking.

    Returns:
        Public facts about each visible person: ID, name, cell, seat and table, whether they
        are free to talk (in no conversation and in no hurry), the conversation they are in,
        whether they stand beside the viewer (`scenes.side_by_side`), and their current action
        verb and target name. Needs, inventory, traits and memories stay private.

    Raises:
        ValueError: Visitor ID does not exist.
    """
    actor = find_actor(world, actor_id)
    if actor is None:
        raise ValueError("Unknown visitor")
    return people_in_sight(world, actor)
