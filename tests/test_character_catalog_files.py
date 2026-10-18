"""The filesystem catalog requires complete role-specific eight-view art."""

import json
import struct
from pathlib import Path
from typing import Any

import pytest

from tavern.adapters.characters import BARTENDER_POSES, DIRECTIONS, GUEST_POSES, load_catalog
from tavern.evening.scenario import parse_scenario
from tavern.mind.cards import PARAMS


def character() -> dict[str, Any]:
    """Build the profile fields unrelated to files."""
    return {"id": "ada", "role": "guest", "name": "Ada", "color": "#a08060", "looks": "the drover",
            "occupation": "drover", "background": "Drives cattle.", "temperament": "Calm.", "speech": "Slow.",
            "quirks": "Counts mugs.", "secret": "Lost a herd.", "goal": "Rest.", "sex": "female",
            "params": dict.fromkeys(PARAMS, 0.5), "carries": {}}


def png(size: int = 68) -> bytes:
    """Build the signature and transparent RGBA header the catalog checks."""
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I4sIIBBBBB", 13, b"IHDR", size, size, 8, 6, 0, 0, 0)


def catalog(tmp_path: Path, missing: tuple[str, str] | None = None, cast: str = "locals", role: str = "guest",
            character_id: str = "ada") -> Path:
    """Write a complete single-character catalog under one cast folder, optionally omitting one image."""
    folder = tmp_path / cast / character_id
    folder.mkdir(parents=True)
    (folder / "character.json").write_text(json.dumps({**character(), "id": character_id, "role": role}))
    (folder / "relationships.json").write_text("[]")
    (folder / "visuals.json").write_text(json.dumps({"size": 68, "lift": -16}))
    for pose in GUEST_POSES if role == "guest" else BARTENDER_POSES:
        for direction in DIRECTIONS:
            if (pose, direction) != missing:
                path = folder / "art" / pose / "rotations" / f"{direction}.png"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(png())
    return tmp_path


def test_load_catalog_reads_a_complete_character_directory(tmp_path: Path) -> None:
    loaded = load_catalog(catalog(tmp_path))
    assert (loaded.character("ada")["card"]["sprite"], loaded.public()["characters"][0]["sprite"]) == ("ada", "ada")


@pytest.mark.parametrize("cast, role", [
    pytest.param("locals", "guest", id="local"),
    pytest.param("guests", "guest", id="famous-guest"),
    pytest.param("staff", "bartender", id="staff"),
])
def test_the_folder_is_the_cast(tmp_path: Path, cast: str, role: str) -> None:
    loaded = load_catalog(catalog(tmp_path, cast=cast, role=role))
    assert (loaded.character("ada")["cast"], loaded.public()["characters"][0]["cast"]) == (cast, cast)


@pytest.mark.parametrize("cast, role, message", [
    pytest.param("locals", "bartender", "staff", id="bartender-among-locals"),
    pytest.param("guests", "bartender", "staff", id="bartender-among-guests"),
    pytest.param("staff", "guest", "staff", id="guest-among-staff"),
    pytest.param("regulars", "guest", "regulars", id="unknown-cast-folder"),
])
def test_load_catalog_refuses_a_role_outside_its_cast(tmp_path: Path, cast: str, role: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_catalog(catalog(tmp_path, cast=cast, role=role))


def test_load_catalog_refuses_one_id_in_two_casts(tmp_path: Path) -> None:
    catalog(tmp_path, cast="locals")
    catalog(tmp_path, cast="guests")
    with pytest.raises(ValueError, match="ada"):
        load_catalog(tmp_path)


@pytest.mark.parametrize("missing, message", [
    pytest.param(("Idle", "north-east"), "north-east", id="missing-diagonal"),
    pytest.param(("Fighting", "south"), "Fighting", id="missing-guest-pose"),
])
def test_load_catalog_refuses_incomplete_eight_view_art(tmp_path: Path, missing: tuple[str, str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_catalog(catalog(tmp_path, missing))


def test_repository_scenario_resolves_catalog_defaults() -> None:
    root = Path(__file__).resolve().parents[1]
    loaded = load_catalog(root / "characters")
    scenario = parse_scenario(json.loads((root / "data" / "scenarios" / "locals.json").read_text()), catalog=loaded)
    edda = next(guest for guest in scenario.guests if guest["id"] == "edda")
    assert (edda["sprite"], edda["carries"], len(scenario.ties), scenario.staff[0]["card"]["id"]) == (
        "edda", {"remedy": 3}, 3, "hob")


@pytest.mark.parametrize("scenario, cast, guests", [
    pytest.param("locals", "locals", ["edda", "rurik", "toren", "brida", "calder", "saye"], id="locals-evening"),
    pytest.param("guests", "guests", ["musk", "tyson", "trump", "greta"], id="guests-evening"),
])
def test_each_cast_has_a_scenario_of_its_own_people(scenario: str, cast: str, guests: list[str]) -> None:
    root = Path(__file__).resolve().parents[1]
    loaded = load_catalog(root / "characters")
    parsed = parse_scenario(json.loads((root / "data" / "scenarios" / f"{scenario}.json").read_text()), catalog=loaded)
    assert [guest["id"] for guest in parsed.guests] == guests
    assert {loaded.character(guest["id"])["cast"] for guest in parsed.guests} == {cast}
    assert [loaded.character(member["id"])["cast"] for member in parsed.staff] == ["staff"]
