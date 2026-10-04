"""Atomic JSON snapshots of the authoritative world."""

import json
import math
from pathlib import Path
from typing import Any, Mapping, cast

from tavern.body.drunkenness import check_drunkenness
from tavern.body.expression import check_saved_expression
from tavern.body.hearing import check_saved_stimuli
from tavern.body.queues import check_saved_lines
from tavern.evening.scenario import check_saved_expected
from tavern.hall.arrival import check_saved_visit
from tavern.hall.lifecycle import check_saved_progress, check_saved_seat
from tavern.hall.navigation import find_path
from tavern.hall.rules import check_rules
from tavern.hall.sight import check_saved_knowledge
from tavern.hall.state import World
from tavern.hall.validation import saved_cell
from tavern.hall.world import create_world
from tavern.mind.cards import parse_card
from tavern.mind.intentions import check_saved_intention
from tavern.social.heard import check_heard
from tavern.social.invitations import KINDS, check_invitations
from tavern.social.scenes import check_saved_scenes
from tavern.social.thoughts import check_mind
from tavern.social.ties import parse_own_ties


def save_world(world: Mapping[str, Any], path: Path) -> None:
    """Save all serializable simulation state atomically.

    Args:
        world: Current authoritative state, including ongoing actions.
        path: Destination snapshot file.
    Raises:
        ValueError: State cannot be serialized or the file cannot be written.
    """
    try:
        encoded = json.dumps(world, indent=2, allow_nan=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(encoded + "\n")
        temporary.replace(path)
    except (OSError, TypeError, ValueError) as error:
        raise ValueError(f"Could not save the world: {error}") from error


def _validate_clock(world: Mapping[str, Any]) -> None:
    for key in ("time", "speed", "tick"):
        value = world.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"Invalid saved {key}")
    if world["time"] < 0 or world["tick"] < 0 or not 0.25 <= world["speed"] <= 8:
        raise ValueError("Saved clock is outside supported limits")
    if not isinstance(world.get("paused"), bool):
        raise ValueError("Invalid saved pause state")


def _validate_actor_runtime(world: Mapping[str, Any]) -> None:
    actor_ids = {actor["id"] for actor in world["actors"]}
    verbs = set(world["rules"]["durations"])
    for actor in world["actors"]:
        if actor.get("status") not in {"idle", "walking", "interacting", "waiting", "queued"}:
            raise ValueError("Invalid saved actor status")
        action = actor.get("action")
        if action is not None and (not isinstance(action, dict) or action.get("verb") not in verbs):
            raise ValueError("Invalid saved actor action")
        if not all(isinstance(actor.get(key), dict) for key in ("knowledge", "inventory", "decision")):
            raise ValueError("Incomplete saved actor state")
        if not isinstance(actor.get("memory"), list):
            raise ValueError("Invalid saved memories")
        if not isinstance(actor.get("sprite"), str) or not actor["sprite"]:
            raise ValueError("Invalid saved sprite")
        knowledge = actor["knowledge"]
        if not isinstance(knowledge.get("objects"), dict) or not isinstance(knowledge.get("cells"), list):
            raise ValueError("Invalid saved knowledge")
        for cell in knowledge["cells"]:
            saved_cell(cell, world["map"])
        check_saved_knowledge(knowledge["objects"], world)
        check_saved_progress(actor, world["map"])
        check_saved_seat(actor, world)
        check_saved_visit(actor.get("visit"))
        check_mind(actor)
        check_heard(actor, world["rules"])
        check_drunkenness(actor, world["rules"])
        check_saved_expression(actor, world)
        _validate_character(actor)
        check_saved_intention(actor)
    for item in world["map"]["objects"]:
        if item.get("reserved_by") is not None and item["reserved_by"] not in actor_ids:
            raise ValueError("Saved reservation belongs to an unknown actor")


def _validate_geometry(world: Mapping[str, Any]) -> None:
    world_map = world["map"]
    # Dynamic obstacles may cover a valid interaction spot at save time.
    # Validate object geometry separately, then validate all obstacle coordinates.
    create_world({**world_map, "blocked": [], "actors": world["actors"]})
    find_path((0, 0), (0, 0), world_map["width"], world_map["height"], world_map["blocked"])
    if any([actor["x"], actor["y"]] in world_map["blocked"] for actor in world["actors"]):
        raise ValueError("Saved visitor occupies a blocked cell")


def _validate_departed(world: Mapping[str, Any]) -> None:
    departed = world.get("departed")
    if not isinstance(departed, list) or any(not isinstance(item, dict) for item in departed):
        raise ValueError("Invalid saved departures")
    ids = [item.get("id") for item in [*world["actors"], *departed]]
    if any(not isinstance(item, str) for item in ids) or len(set(ids)) != len(ids):
        raise ValueError("Saved visitors need unique IDs")
    for item in departed:
        check_saved_visit(item.get("visit"))
        check_mind(item)
        check_heard(item, world["rules"])
        check_drunkenness(item, world["rules"])
        check_saved_intention(item)
        if "left_at" not in item["visit"]:
            raise ValueError("Departed visitor has no departure time")


def _validate_character(actor: Mapping[str, Any]) -> None:
    # A visitor not cast from a card (the room's own, or an inline scenario guest) has none.
    if actor["card"] is not None:
        parse_card(actor["card"])
    parse_own_ties(actor["ties"])


class FileStore:
    """One session's worlds in JSON files: the manual save at a path, the autosave beside it."""

    def __init__(self, manual: Path) -> None:
        """Create a store.

        Args:
            manual: File of the manual save; the autosave is `autosave.json` in the same folder.
        """
        self.manual = manual

    def _path(self, slot: str) -> Path:
        return self.manual if slot == "manual" else self.manual.with_name("autosave.json")

    def load(self, slot: str) -> World | None:
        """Read a saved world.

        Args:
            slot: `manual` or `auto`.

        Returns:
            The validated world, or None when nothing was saved in that slot.

        Raises:
            ValueError: The file is unreadable or invalid.
        """
        path = self._path(slot)
        return load_world(path) if path.is_file() else None

    def save(self, world: Mapping[str, Any], slot: str) -> None:
        """Write a world atomically.

        Args:
            world: Current authoritative state.
            slot: `manual` or `auto`.

        Raises:
            ValueError: The world cannot be serialized or written.
        """
        save_world(world, self._path(slot))


def parse_world(encoded: str) -> World:
    """Validate a serialized world before it replaces the running state.

    Args:
        encoded: JSON snapshot from a file or database.
    Returns:
        Complete world with action progress and memories preserved.
    Raises:
        ValueError: The snapshot is malformed or uses an unsupported state shape.
    """
    try:
        world = json.loads(encoded)
        if not isinstance(world, dict) or world.get("schema_version") != 6:
            raise ValueError("Unsupported snapshot version")
        json.dumps(world, allow_nan=False)
        _validate_clock(world)
        _validate_geometry(world)
        check_rules(world)
        _validate_actor_runtime(world)
        check_saved_lines(world)
        _validate_departed(world)
        check_saved_expected(world)
        check_saved_stimuli(world)
        check_saved_scenes(world, KINDS)
        check_invitations(world)
        if not isinstance(world.get("events"), list):
            raise ValueError("Invalid saved event log")
        return cast(World, world)  # Every part is validated above.
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ValueError(f"Could not load the world: {error}") from error


def load_world(path: Path) -> World:
    """Read and validate a saved world from disk.

    Args:
        path: Existing snapshot file.
    Returns:
        Validated world state.
    Raises:
        ValueError: The file is missing, unreadable, or invalid.
    """
    try:
        return parse_world(path.read_text())
    except OSError as error:
        raise ValueError(f"Could not load the world: {error}") from error
