"""Authoritative character profiles and their default relationships."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from tavern.body.items import parse_carries
from tavern.mind.cards import Card, PERSONA_LISTS, PERSONA_TEXT, TEXT_FIELDS, parse_card
from tavern.social.ties import Tie, parse_ties


ROLES = ("guest", "bartender")
CASTS = ("locals", "guests", "staff")
COMMON_POSES = ("Idle", "Seated", "Darts", "Bathroom", "Drinking", "DrinkingSeated", "TalkingSeated", "TakeBeer",
                "Walking", "Talking", "Giving", "GivingSeated", "Receiving", "ReceivingSeated", "SleepingSeated")
ROLE_POSES = {
    "guest": (*COMMON_POSES, "Fighting", "KnockedOut", "Hurt", "HurtSeated", "Shoving", "HelpingUp"),
    "bartender": (*COMMON_POSES, "PouringBeer"),
}


class Visuals(TypedDict):
    """How the browser draws one character's full art set."""

    size: int
    lift: int


class Character(TypedDict):
    """A profile resolved from one character directory."""

    id: str
    role: Literal["guest", "bartender"]
    cast: Literal["locals", "guests", "staff"]
    name: str
    color: str
    card: Card
    carries: dict[str, int]
    visuals: Visuals


@dataclass(frozen=True)
class Catalog:
    """Validated catalog content, independent of its filesystem storage."""

    characters: dict[str, Character]
    ties: tuple[Tie, ...]

    def character(self, character_id: str) -> Character:
        """Return one character by stable ID.

        Args:
            character_id: Profile ID.
        Returns:
            The profile.
        Raises:
            ValueError: The ID is absent.
        """
        if character_id not in self.characters:
            raise ValueError(f"Unknown character {character_id!r}")
        return self.characters[character_id]

    def guest(self, character_id: str) -> Character:
        """Return a catalog character who may attend as a guest.

        Args:
            character_id: Profile ID.
        Returns:
            A guest profile.
        Raises:
            ValueError: The ID is absent or belongs to another role.
        """
        character = self.character(character_id)
        if character["role"] != "guest":
            raise ValueError(f"Character {character_id!r} is not a guest")
        return character

    def bartender(self, character_id: str) -> Character:
        """Return a catalog character who may staff a bar.

        Args:
            character_id: Profile ID.
        Returns:
            A bartender profile.
        Raises:
            ValueError: The ID is absent or belongs to another role.
        """
        character = self.character(character_id)
        if character["role"] != "bartender":
            raise ValueError(f"Character {character_id!r} is not a bartender")
        return character

    def public(self) -> dict[str, list[dict[str, object]]]:
        """Return display and rendering data safe to send to a browser.

        Returns:
            Alphabetically ordered public records without the model-only card text.
        """
        return {"characters": [
            {"id": item["id"], "role": item["role"], "cast": item["cast"], "name": item["name"], "color": item["color"],
             "sprite": item["id"], "visuals": {**item["visuals"], "poses": list(ROLE_POSES[item["role"]])}}
            for item in sorted(self.characters.values(), key=lambda character: character["id"])
        ]}


def parse_catalog(records: Sequence[Any]) -> Catalog:
    """Validate profile records and resolve their default relationship pairs.

    Args:
        records: Character records, each including its relationship records and display visuals.
    Returns:
        Characters by ID and the catalog's undirected default ties.
    Raises:
        ValueError: A profile is malformed, IDs repeat, or a relationship is invalid.
    """
    if not isinstance(records, Sequence) or isinstance(records, str) or not records:
        raise ValueError("Character catalog must be a nonempty list")
    characters = [_character(record) for record in records]
    ids = [item["id"] for item, _ in characters]
    duplicate = next((character_id for character_id in ids if ids.count(character_id) > 1), None)
    if duplicate is not None:
        raise ValueError(f"Duplicate character {duplicate!r}")
    ties = _ties(characters, ids)
    return Catalog(characters={item["id"]: item for item, _ in characters}, ties=ties)


def _character(data: Any) -> tuple[Character, list[dict[str, Any]]]:
    if not isinstance(data, Mapping):
        raise ValueError("Character must be a mapping")
    required = {"id", "role", "cast", "color", "carries", "relationships", "visuals", *TEXT_FIELDS, "sex", "params"}
    optional = {"looks", "origin", *PERSONA_TEXT, *PERSONA_LISTS}
    missing, unknown = required - data.keys(), data.keys() - required - optional
    if missing or unknown:
        raise ValueError(f"Character is missing {sorted(missing)} or has unknown {sorted(unknown)}")
    character_id = data["id"]
    if not isinstance(character_id, str) or not character_id or not character_id.isidentifier():
        raise ValueError(f"Character id must be a nonempty identifier, not {character_id!r}")
    role = data["role"]
    if role not in ROLES:
        raise ValueError(f"Character role must be one of {', '.join(ROLES)}, not {role!r}")
    cast = data["cast"]
    if cast not in CASTS:
        raise ValueError(f"Character cast must be one of {', '.join(CASTS)}, not {cast!r}")
    if (role == "bartender") != (cast == "staff"):
        raise ValueError(f"Character {character_id!r} is a {role} in the {cast} cast: bartenders live only in staff")
    color = data["color"]
    if not isinstance(color, str) or not color.startswith("#") or len(color) != 7:
        raise ValueError(f"Character color must be a #RRGGBB string, not {color!r}")
    visuals = _visuals(data["visuals"])
    relationships = data["relationships"]
    if not isinstance(relationships, list):
        raise ValueError("Character relationships must be a list")
    card_data = {key: data[key] for key in (*TEXT_FIELDS, "sex", "params")} | {"id": character_id, "sprite": character_id}
    card_data |= {key: data[key] for key in optional if key in data}
    card = parse_card(card_data)
    return (Character(id=character_id, role=role, cast=cast, name=card["name"], color=color, card=card,
                      carries=parse_carries(data["carries"]), visuals=visuals), relationships)


def _visuals(value: Any) -> Visuals:
    if not isinstance(value, Mapping) or set(value) != {"size", "lift"}:
        raise ValueError("Character visuals must have exactly size and lift")
    if type(value["size"]) is not int or value["size"] <= 0:
        raise ValueError("Character visual size must be a positive whole number")
    if type(value["lift"]) is not int:
        raise ValueError("Character visual lift must be a whole number")
    return Visuals(size=value["size"], lift=value["lift"])


def _ties(characters: Sequence[tuple[Character, list[dict[str, Any]]]], ids: Sequence[str]) -> tuple[Tie, ...]:
    records: list[dict[str, Any]] = []
    for character, relationships in characters:
        for relationship in relationships:
            if not isinstance(relationship, Mapping) or set(relationship) != {"with", "kind", "note"}:
                raise ValueError("Character relationship has exactly with, kind and note")
            if relationship["with"] not in ids:
                raise ValueError(f"Character relationship names unknown character {relationship['with']!r}")
            records.append({"a": character["id"], "b": relationship["with"],
                            "kind": relationship["kind"], "note": relationship["note"]})
    try:
        return parse_ties(records, ids)
    except ValueError as error:
        message = str(error)
        if message == "Two guests may share only one starting relationship":
            raise ValueError("Duplicate character relationship pair") from error
        raise ValueError(message.replace("guest", "character")) from error
