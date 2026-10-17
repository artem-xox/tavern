"""Filesystem loading and art validation for the authored character catalog."""

import json
import struct
from pathlib import Path
from typing import Any

from tavern.mind.characters import CASTS, Catalog, ROLE_POSES, parse_catalog


DIRECTIONS = ("north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west")
GUEST_POSES = ROLE_POSES["guest"]
BARTENDER_POSES = ROLE_POSES["bartender"]
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def load_catalog(root: Path) -> Catalog:
    """Read, validate, and resolve every character directory below a catalog root.

    Args:
        root: Directory with one folder per cast (locals, guests, staff), each holding one profile directory
            per character. The folder is the character's cast.
    Returns:
        A validated catalog ready for scenario casting and browser publication.
    Raises:
        ValueError: The root, a cast folder, JSON data, directory name, role-specific art, or a PNG is invalid.
        OSError: A required catalog file cannot be read.
    """
    if not root.is_dir():
        raise ValueError(f"Character catalog directory is missing: {root}")
    folders = sorted(folder for cast in _cast_folders(root) for folder in cast.iterdir() if folder.is_dir())
    if not folders:
        raise ValueError("Character catalog has no character directories")
    records = [_record(folder) for folder in folders]
    catalog = parse_catalog(records)
    for folder in folders:
        character = catalog.character(folder.name)
        _check_art(folder, character["role"], character["visuals"]["size"])
    return catalog


def _cast_folders(root: Path) -> list[Path]:
    folders = sorted(path for path in root.iterdir() if path.is_dir())
    unknown = next((folder.name for folder in folders if folder.name not in CASTS), None)
    if unknown is not None:
        raise ValueError(f"Unknown cast folder {unknown!r} in {root}: expected {', '.join(CASTS)}")
    return folders


def _record(folder: Path) -> dict[str, Any]:
    character = _json(folder / "character.json")
    if not isinstance(character, dict):
        raise ValueError(f"Character file must be an object: {folder / 'character.json'}")
    if character.get("id") != folder.name:
        raise ValueError(f"Character ID {character.get('id')!r} does not match directory {folder.name!r}")
    relationships = _json(folder / "relationships.json")
    visuals = _json(folder / "visuals.json")
    # The folder is the cast; character.json never says it, so a card cannot disagree with where it lives.
    return {**character, "cast": folder.parent.name, "relationships": relationships, "visuals": visuals}


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {path}: {error.msg}") from error


def _check_art(folder: Path, role: str, size: int) -> None:
    for pose in _poses(role):
        for direction in DIRECTIONS:
            path = folder / "art" / pose / "rotations" / f"{direction}.png"
            _check_png(path, size)


def _poses(role: str) -> tuple[str, ...]:
    if role not in ROLE_POSES:
        raise ValueError(f"Unknown character role {role!r}")
    return ROLE_POSES[role]


def _check_png(path: Path, size: int) -> None:
    if not path.is_file():
        raise ValueError(f"Missing character art: {path}")
    data = path.read_bytes()
    if len(data) < 29 or not data.startswith(_PNG_SIGNATURE) or data[12:16] != b"IHDR":
        raise ValueError(f"Character art is not a PNG: {path}")
    width, height = struct.unpack(">II", data[16:24])
    if (width, height) != (size, size):
        raise ValueError(f"Character art has {width}x{height}, expected {size}x{size}: {path}")
    if data[25] not in (4, 6):
        raise ValueError(f"Character art has no alpha channel: {path}")
