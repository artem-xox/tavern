"""Serializable authoritative tavern state and physical action execution."""

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from tavern.body.actions import action_error
from tavern.body.activities import ACTIVITIES
from tavern.body.attention import attend
from tavern.body.bartending import tend_bar
from tavern.body.dozing import nodding_off, show_sleep
from tavern.body.drunkenness import wear_off
from tavern.body.energy import tire
from tavern.body.expression import update_expression
from tavern.body.fights import Fight, begin_waiting, engage_defenders, run_fights
from tavern.body.projects import honor_projects, open_project
from tavern.body.queues import check_lines, cut_in, line_of, must_wait
from tavern.body.wounds import RECOVER, step_wounds
from tavern.hall.arrival import admit_arrivals, arrival_ranges, arriving, create_actor
from tavern.hall.closing import call_closing, call_last_orders, closing_called, inn_closed, since_last_call
from tavern.hall.lifecycle import (activate, clear_action, complete_action, finish_parts, line_up, look, notice_target,
                              reject, step_actor, talk_in_line)
from tavern.hall.memory import record_event
from tavern.hall.room import create_map
from tavern.hall.routes import plan_route
from tavern.hall.rules import default_rules
from tavern.hall.sight import look_around, people_in_sight, visible_cells
from tavern.hall.staff import check_staff_cells, on_staff
from tavern.hall.state import World, find_actor
from tavern.hall.validation import number, unique_ids
from tavern.social.aftermath import keep_cursing
from tavern.social.bystanders import note_started
from tavern.social.dice import settle_games
from tavern.social.commitments import promises_of, settle_commitments
from tavern.social.errands import honor_invitations
from tavern.social.responses import mark_answered
from tavern.social.invitations import errand_parties, invitations_of
from tavern.social.tables import mark_ownership
from tavern.social.scenes import check_conversations
from tavern.social.thoughts import forget_expired
from tavern.social.turns import speak_turns


def create_world(map_data: Mapping[str, Any], seed: int = 0) -> World:
    """Create and validate an independently owned, serializable room snapshot.

    Args:
        map_data: Flat room definition with geometry, objects, and initial actors. An optional
            `arrival` section maps needs to [low, high] ranges: visitors then arrive with needs
            drawn from them and look around the hall as they come in. An optional `table_manners` (true or
            false, default false) asks guests to mind whose table is whose (`rules.manners`).
        seed: Saved deterministic seed of the evening's arrivals and decision policy.

    Returns:
        New world state containing no references to the supplied room definition. Nobody
        else is expected and the inn never closes; `scenario.open_evening` sets both.

    Raises:
        ValueError: Layout, IDs, resources, arrival ranges, or actor values are invalid.
    """
    world_map = create_map(map_data)
    check_staff_cells(world_map)
    unique_ids(map_data.get("actors", []), "actor")
    ranges, listed = arrival_ranges(map_data), map_data.get("actors", [])
    actors = [create_actor(item, world_map)
              for item in (listed if ranges is None else arriving(listed, ranges, seed))]
    if len({(item["x"], item["y"]) for item in actors}) != len(actors):
        raise ValueError("Actors cannot overlap at startup")
    rules = default_rules()
    manners = map_data.get("table_manners", False)
    if type(manners) is not bool:
        raise ValueError(f"The layout's table_manners must be true or false, not {manners!r}")
    rules["manners"]["table_intrusion"] = manners
    world = World(schema_version=19, seed=seed, tick=0, time=0.0, paused=False, speed=1.0,
                  map=world_map, actors=actors, departed=[], expected=[], closes_at=None, last_call_at=None,
                  events=[], stimuli=[], next_stimulus_id=0, conversations=[], next_conversation_id=0,
                  commitments=[], invitations=[], projects=[], news=[], fights=[], rules=rules)
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
    if on_staff(actor):
        # Only the bar's own routine (`tavern.body.bartending`) moves staff, not a decision or an operator.
        return {"accepted": False, "reason": f"{actor['name']} works behind the bar"}
    verb = action.get("verb")
    activity = ACTIVITIES.get(verb) if isinstance(verb, str) else None
    if activity is not None and activity.opens_project:
        # A plan, not an action: the project's own steps start the actions (`tavern.body.projects`).
        return open_project(world, actor, activity.opens_project, action.get("target_id"))
    cutting = action.get("verb") == "cut_in_line"
    action, reason = cut_in(world, action)
    reason = reason or action_error(world, actor, action) or _last_call_error(world, action)
    if reason:
        notice_target(world, actor, action)
        return reject(world, actor, reason)
    activity = ACTIVITIES[action["verb"]]
    if activity.partner and not activity.approaches and line_of(world, actor_id) is not None:
        return talk_in_line(world, actor, action)
    if must_wait(world, actor, action):
        return line_up(world, actor, action, cutting)
    plan = plan_route(world, actor, action)
    if plan is None:
        return reject(world, actor, "No reachable interaction spot")
    activate(world, actor, action, plan)
    mark_answered(world, actor, action)
    return {"accepted": True, "reason": None}


def _last_call_error(world: Mapping[str, Any], action: Mapping[str, Any]) -> str | None:
    # Only a new order is refused once the barkeep has called closing time: one made before it is still served.
    refusal = ACTIVITIES[action["verb"]].stopped_at_last_call
    return refusal if refusal and closing_called(world) else None


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
    engage_defenders(world, activate)
    for actor in world["actors"]:
        step_actor(world, actor, elapsed)
    cursing = _fall_and_rise(world)
    _see_off(world)
    call_last_orders(world, since)
    call_closing(world, since)
    admit_arrivals(world)
    check_conversations(world)
    speak_turns(world)
    honor_invitations(world, start_action)
    honor_projects(world, start_action)
    settle_commitments(world)
    tend_bar(world)
    games = settle_games(world)
    for actor in games.done:
        complete_action(world, actor)
    for actor in games.released:
        clear_action(world, actor)
    for actor in attend(world):
        clear_action(world, actor)
    # Two who broke apart still hot go on cursing, once this tick's sounds have drawn their glances.
    for fight in cursing:
        keep_cursing(world, fight)
    wear_off(world, elapsed)
    tire(world, elapsed)
    for actor in nodding_off(world, elapsed):
        activate(world, actor, {"id": "doze", "verb": "doze", "target_id": None}, (None, []))
    finish_parts(world)
    update_expression(world)
    show_sleep(world)


def _fall_and_rise(world: World) -> list[Fight]:
    # Fights run their exchanges and end, and their next duel (a bystander waiting a turn) begins; then whoever is laid
    # low goes down, whoever is up again stands, and whoever was knocked out and left untreated slips away home.
    # Returns the fights that ended in shouting.
    bouts = run_fights(world)
    for actor in bouts.released:
        clear_action(world, actor)
    begin_waiting(world, activate, bouts.ended)
    engage_defenders(world, activate)
    note_started(world)
    stepped = step_wounds(world)
    for actor in stepped.released:
        clear_action(world, actor)
    for actor in stepped.fallen:
        activate(world, actor, {"id": RECOVER, "verb": RECOVER, "target_id": None}, (None, []))
    door = next((item for item in world["map"]["objects"] if item["kind"] == "door"), None)
    for actor in stepped.sent_home:
        if door is not None and actor["action"] is None:
            record_event(world, actor, "limped_home", f"{actor['name']}, battered, slipped out of the inn to go home")
            start_action(world, actor["id"], {"id": f"leave:{door['id']}", "verb": "leave", "target_id": door["id"]})
    return bouts.shouting


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
        Own actor state, known object records (chairs marked with whose seat they are, tables with whose table), personal memories, map bounds, visible
        cells, whether the inn has closed, the rules of giving, and who is on an errand (`on_errands`). Unseen resource changes remain
        remembered historical values.

    Raises:
        ValueError: Visitor ID does not exist.
    """
    actor = find_actor(world, actor_id)
    if actor is None:
        raise ValueError("Unknown visitor")
    visible = look(world, actor)
    objects = deepcopy(list(actor["knowledge"]["objects"].values()))
    mark_ownership(world, actor, objects)
    return {"actor": deepcopy(actor), "objects": objects,
            "visitors": _visible_visitors(world, actor),
            "memory": deepcopy(actor["memory"][-10:]), "visible_cells": visible, "time": world["time"],
            "invitations": invitations_of(world, actor), "promises": promises_of(world, actor_id),
            "map": {"width": world["map"]["width"], "height": world["map"]["height"]},
            "closed": inn_closed(world), "called_closing": since_last_call(world), "giving": dict(world["rules"]["giving"]),
            "on_errands": errand_parties(world)}


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
