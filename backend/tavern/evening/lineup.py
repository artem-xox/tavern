"""The lineup: the evening a player builds on the start screen from a cast's scenario, and the casts offered."""

from collections.abc import Mapping, Sequence
from typing import Any

from tavern.body.ailment import eligible
from tavern.evening.scenario import Scenario, parse_scenario
from tavern.hall.validation import number
from tavern.mind.characters import Catalog

MIN_GUESTS, MAX_GUESTS = 1, 6
MIN_MINUTES, MAX_MINUTES = 1, 60
# Seconds between one guest coming in and the next, so the door never sends a crowd to the bar at once.
ENTRY_GAP = 15.0
# A short evening squeezes the entries into this share of its length.
ENTRY_SHARE = 0.5
# The barkeep calls closing time when this share of the evening has passed.
LAST_CALL_SHARE = 0.9
CAST_TITLES = {"locals": "Locals", "guests": "Guests"}
# Casts whose guests are public figures who know one another by name before they meet.
FAMOUS_CASTS = ("guests",)


def lineup_scenario(templates: Mapping[str, Mapping[str, Any]], catalog: Catalog, cast: str,
                    character_ids: Any, minutes: Any) -> Scenario:
    """Build a cast's evening for the picked guests.

    The cast's template keeps its needs and staff. The picked guests are due at opening and the opening window
    spaces them `ENTRY_GAP` seconds apart (closer in a short evening, within its first half), so a late arrival
    never outlasts the evening and no crowd reaches the bar at once; its news is cut down to what the picked
    guests know.

    Args:
        templates: Raw scenario data by cast ID (`locals`, `guests`).
        catalog: Every character, to cast the picked guests from.
        cast: ID of the cast to take the template from.
        character_ids: IDs of the picked guests, from 1 to 6, each once, all of that cast; their order is kept.
        minutes: Length of the evening in minutes of game time, from 1 to 60.
    Returns:
        The validated scenario.
    Raises:
        ValueError: The cast is unknown, the guests are not a list of 1 to 6 distinct characters of that cast,
            or the length is out of range.
    """
    if cast not in templates:
        raise ValueError(f"Unknown cast {cast!r}")
    ids = _picked(character_ids, catalog, cast)
    length = number(minutes, "Evening length", MIN_MINUTES, MAX_MINUTES) * 60
    gap = min(ENTRY_GAP, length * ENTRY_SHARE / max(len(ids) - 1, 1))
    data = {**templates[cast], "closes_at": length, "opening_window": [1, 1 + gap * (len(ids) - 1)],
            "last_call_at": length * LAST_CALL_SHARE,
            "guests": [{"character": item, "arrives_at": 0} for item in ids], **_news_for(templates[cast], ids)}
    if cast in FAMOUS_CASTS:
        data["relationships"] = [*data.get("relationships", []), *_well_known(ids, data.get("relationships", []))]
    # An unwell guest must carry no cure; a lone healer, say, has nobody to fall ill, so they come in well.
    if not eligible([{"carries": catalog.character(item)["carries"]} for item in ids]):
        data.pop("ailment", None)
    return parse_scenario(data, catalog=catalog)


def _well_known(ids: Sequence[str], tied: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    # Every pair the template does not already tie, in picked order.
    held = {frozenset((item["a"], item["b"])) for item in tied}
    return [{"a": a, "b": b, "kind": "well known", "note": "Each knows the other by name and reputation."}
            for i, a in enumerate(ids) for b in ids[i + 1:] if frozenset((a, b)) not in held]


def _picked(character_ids: Any, catalog: Catalog, cast: str) -> list[str]:
    if not isinstance(character_ids, list) or not all(isinstance(item, str) for item in character_ids):
        raise ValueError("Lineup guests must be a list of character IDs")
    if not MIN_GUESTS <= len(character_ids) <= MAX_GUESTS:
        raise ValueError(f"A lineup seats {MIN_GUESTS} to {MAX_GUESTS} guests, not {len(character_ids)}")
    repeated = next((item for item in character_ids if character_ids.count(item) > 1), None)
    if repeated is not None:
        raise ValueError(f"Lineup names {repeated!r} twice")
    for item in character_ids:
        if catalog.character(item)["cast"] != cast:
            raise ValueError(f"Character {item!r} is not in the {cast} cast")
    return character_ids


def _news_for(template: Mapping[str, Any], ids: Sequence[str]) -> dict[str, Any]:
    # Each item is kept for the picked guests who know it; one nobody picked knows could never be told.
    news = [{**item, "known_by": [who for who in item["known_by"] if who in ids]} for item in template.get("news", [])]
    news = [item for item in news if item["known_by"]]
    told = template.get("news_tonight")
    # `news_tonight` of None means every item is told, which is all an evening of one or two items can do.
    return {"news": news, "news_tonight": min(told, len(news)) if told and news else None}


def casts_public(catalog: Catalog, templates: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """List the casts a player can pick from, with the face each guest shows on the start screen.

    Args:
        catalog: Every character.
        templates: Raw scenario data by cast ID; a cast without one cannot be played.
    Returns:
        One record per cast, ordered by ID: `id`, `title` and its `characters` (`id`, `name`, and a
        `description` taken from the card's occupation), ordered by ID. The rest of the card stays secret.
    """
    return [{"id": cast, "title": CAST_TITLES[cast], "characters": [
        {"id": item["id"], "name": item["name"], "description": item["card"]["occupation"]}
        for item in sorted(catalog.characters.values(), key=lambda character: character["id"])
        if item["cast"] == cast and item["role"] == "guest"]} for cast in sorted(templates)]
