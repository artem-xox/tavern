"""An evening's scenario, separate from the room: who is expected, when, and closing time."""

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from math import inf
import math
from random import Random
from typing import Any, NotRequired, TypedDict, cast

from tavern.body.ailment import draw_ailing, eligible, parse_ailment
from tavern.body.items import parse_carries
from tavern.hall.arrival import admit_arrivals, arrival_ranges, arriving, take_posts
from tavern.hall.state import World
from tavern.hall.validation import number, unique_ids
from tavern.hall.world import create_world
from tavern.mind.cards import Card, parse_card
from tavern.social.facts import News, draw_news, parse_news
from tavern.social.ties import OwnTie, Tie, own_ties, parse_own_ties, parse_ties


class Guest(TypedDict):
    """A guest the scenario expects tonight; `arrives_at` is in game seconds after opening.

    A guest cast from a character card carries the `card`, and their `traits` are its params.
    A guest with starting relationships carries them as `ties`, from their own side, and one who comes
    in with something in hand or pocket lists it as `carries`.
    """

    id: str
    name: str
    color: str
    sprite: str
    traits: dict[str, float]
    arrives_at: float
    card: NotRequired[Card]
    ties: NotRequired[list[OwnTie]]
    carries: NotRequired[dict[str, int]]


class StaffMember(TypedDict):
    """Someone the scenario puts to work behind a bar: a guest's fields but `arrives_at`, and a `post`.

    `post` is the ID of the bar they work at (see `tavern.hall.staff`). A member cast from a card
    carries it, and their `traits` are its params.
    """

    id: str
    name: str
    color: str
    sprite: str
    traits: dict[str, float]
    post: str
    card: NotRequired[Card]


class ExpectedGuest(Guest):
    """A guest still on the way, kept in the world's `expected` list with tonight's needs drawn.

    The one guest who comes in unwell tonight (see `tavern.body.ailment`) also has `ailing`.
    """

    needs: dict[str, float]
    ailing: NotRequired[bool]


@dataclass(frozen=True)
class Scenario:
    """A validated evening plan; `closes_at` is in game seconds after opening.

    `last_call_at`, when set, is when the barkeep calls closing time out loud: after the start and before `closes_at`.
    `ailing_fatigue`, when set, makes one guest who carries no cure, drawn by the evening's seed, come in unwell with
    that much tiredness (see `tavern.body.ailment`).

    `ties` are the starting relationships between guests, in listed order: what later
    systems seed opinions and familiarity from. `news` is what the evening's guests start
    out knowing (see `facts`); with `news_tonight`, only that many items, drawn by the evening's seed, are told,
    each known by a single guest. `staff` work the evening and are at their posts before the first guest
    comes in. Guests due at opening come in one by one in a random order, evenly from the first to the
    last second of `opening_window`, instead of all at once.
    """

    guests: tuple[Guest, ...]
    arrival: dict[str, tuple[float, float]]
    closes_at: float
    seed: int | None
    ties: tuple[Tie, ...] = ()
    news: tuple[News, ...] = ()
    staff: tuple[StaffMember, ...] = ()
    opening_window: tuple[float, float] | None = None
    news_tonight: int | None = None
    last_call_at: float | None = None
    ailing_fatigue: float | None = None


def _fields(data: Any, required: set[str], optional: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(data, Mapping):
        raise ValueError(f"{label} must be a mapping")
    missing, unknown = required - data.keys(), data.keys() - required - optional
    if missing or unknown:
        raise ValueError(f"{label} is missing {sorted(missing)} or has unknown {sorted(unknown)}")
    return data


def parse_guest(data: Any) -> Guest:
    """Validate one guest expected tonight.

    Args:
        data: Guest record with exactly `id`, `name`, `color`, `sprite`, `traits` (names to
            0–1 values) and `arrives_at` (game seconds, at least 0), and optionally the `card`
            the guest is cast from, their `ties` (see `ties.own_ties`) and what they `carries` in
            (see `items.parse_carries`).
    Returns:
        The guest, with numbers as floats.
    Raises:
        ValueError: A field is missing, unknown, or malformed, or the guest's name, sprite or
            traits differ from their card's.
    """
    fields = _fields(data, {"id", "name", "color", "sprite", "traits", "arrives_at"}, {"card", "ties", "carries"}, "Guest")
    for key in ("id", "name", "color", "sprite"):
        if not isinstance(fields[key], str) or not fields[key]:
            raise ValueError(f"Guest {key} must be a nonempty string")
    if not isinstance(fields["traits"], Mapping):
        raise ValueError("Guest traits must map names to numbers")
    guest = Guest(id=fields["id"], name=fields["name"], color=fields["color"], sprite=fields["sprite"],
                  traits={name: number(value, name, 0, 1) for name, value in fields["traits"].items()},
                  arrives_at=number(fields["arrives_at"], "Arrival time", 0, inf))
    if "card" in fields:
        guest["card"] = _matching_card(guest, fields["card"])
    if "ties" in fields:
        guest["ties"] = parse_own_ties(fields["ties"])
    if "carries" in fields:
        guest["carries"] = parse_carries(fields["carries"])
    return guest


def parse_staff_member(data: Any) -> StaffMember:
    """Validate one staff member of the evening.

    Args:
        data: Record with exactly `id`, `name`, `color`, `sprite`, `traits` (names to 0–1 values) and
            `post` (the ID of a bar), and optionally the `card` they are cast from.
    Returns:
        The staff member.
    Raises:
        ValueError: A field is missing, unknown or malformed, or the name, sprite or traits differ from
            their card's. Whether the post is a bar with staff cells is checked when the evening opens.
    """
    fields = _fields(data, {"id", "name", "color", "sprite", "traits", "post"}, {"card"}, "Staff member")
    for key in ("id", "name", "color", "sprite", "post"):
        if not isinstance(fields[key], str) or not fields[key]:
            raise ValueError(f"Staff member {key} must be a nonempty string")
    if not isinstance(fields["traits"], Mapping):
        raise ValueError("Staff member traits must map names to numbers")
    member = StaffMember(id=fields["id"], name=fields["name"], color=fields["color"], sprite=fields["sprite"],
                         traits={name: number(value, name, 0, 1) for name, value in fields["traits"].items()},
                         post=fields["post"])
    if "card" in fields:
        member["card"] = _matching_card(member, fields["card"])
    return member


def _matching_card(person: Mapping[str, Any], data: Any) -> Card:
    card = parse_card(data)
    if (card["name"], card["sprite"], card["params"]) != (person["name"], person["sprite"], person["traits"]):
        raise ValueError(f"{person['id']!r} must have the name, sprite and params of card {card['id']!r}")
    return card


def parse_scenario(data: Any, cards: Mapping[str, Card] | None = None,
                   staff_cards: Mapping[str, Card] | None = None) -> Scenario:
    """Validate a scenario read from outside the game.

    Args:
        data: Decoded scenario with `guests`, `arrival` need ranges (as in a room's `arrival`
            section), `closes_at` in game seconds, an optional integer `seed`, an optional `opening_window`
            [first, last] in game seconds (none by default) and optional
            starting `relationships` (see `ties.parse_ties`), optional `news` (see `facts.parse_news`),
            an optional `news_tonight` (how many of the news items are told tonight, from 1 to the number of
            items; every item is told as listed without it), an optional `last_call_at` (game seconds after
            the start, before closing time, when the barkeep calls closing time), an optional `ailment`
            (see `ailment.parse_ailment`: one guest who carries no cure comes in unwell) and optional `staff`
            (see `parse_staff_member`). A guest is either described inline with `traits`, or cast from a character card named by ID in `card`, with
            the card's name and sprite; so is a staff member, from the staff cards.
        cards: Character cards by ID. Without them only the schedule is read: guests cast from
            a card come with no card and middling traits.
        staff_cards: Cards of the staff by ID, kept apart from the guests' so that no staff member is
            offered as a guest. Without them staff cast from a card come with no card and middling traits.
    Returns:
        The scenario, with guests in their listed order, each holding their own ties.
    Raises:
        ValueError: A section is missing, unknown or malformed, the opening window is no [first, last] pair
            ending before closing time, there are no guests, guest or staff
            IDs repeat, a guest would arrive at or after closing time, a guest's or staff member's card
            is unknown or does not match them, a relationship or news item is invalid, or `news_tonight` is
            no whole number from 1 to the number of news items, `last_call_at` is no number after the start
            and before closing time, or the `ailment` is malformed or every guest carries a cure.
    """
    fields = _fields(data, {"guests", "arrival", "closes_at"},
                     {"seed", "relationships", "news", "news_tonight", "last_call_at", "ailment", "staff",
                      "opening_window"}, "Scenario")
    closes_at = number(fields["closes_at"], "Closing time", 0, inf)
    last_call = _last_call_at(fields.get("last_call_at"), closes_at)
    seed = fields.get("seed")
    if seed is not None and type(seed) is not int:
        raise ValueError("Scenario seed must be an integer")
    window = _opening_window(fields.get("opening_window"), closes_at)
    guests = _guests(fields["guests"], closes_at, cards)
    staff = _staff(fields.get("staff", []), guests, staff_cards)
    ties = parse_ties(fields.get("relationships", []), [item["id"] for item in guests])
    news = parse_news(fields.get("news", []), [item["id"] for item in guests])
    told = _news_tonight(fields.get("news_tonight"), len(news))
    ailing = _ailing_fatigue(fields.get("ailment"), guests)
    # `arrival` is a required field above, so its ranges are never None here.
    arrival = cast(dict[str, tuple[float, float]], arrival_ranges(fields))
    return Scenario(guests=_with_ties(guests, ties), arrival=arrival, closes_at=closes_at, seed=seed, ties=ties,
                    news=news, staff=staff, opening_window=window, news_tonight=told, last_call_at=last_call,
                    ailing_fatigue=ailing)


def _ailing_fatigue(value: Any, guests: Sequence[Guest]) -> float | None:
    if value is None:
        return None
    fatigue = parse_ailment(value)
    if not eligible(guests):
        raise ValueError("The scenario's ailment needs a guest who carries no cure to fall ill")
    return fatigue


def _last_call_at(value: Any, closes_at: float) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value < closes_at:
        raise ValueError(f"last_call_at must be a number after the start and before closing time ({closes_at}), not {value!r}")
    return float(value)


def _news_tonight(value: Any, items: int) -> int | None:
    if value is None:
        return None
    if type(value) is not int or not 1 <= value <= items:
        raise ValueError(f"news_tonight must be a whole number from 1 to the {items} news items, not {value!r}")
    return value


def _opening_window(value: Any, closes_at: float) -> tuple[float, float] | None:
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, str) or len(value) != 2:
        raise ValueError("The opening window must be [first, last] in game seconds")
    first, last = (number(item, "Opening window", 0, inf) for item in value)
    if first > last or last >= closes_at:
        raise ValueError("The opening window must run forward and end before closing time")
    return first, last


def _guests(value: Any, closes_at: float, cards: Mapping[str, Card] | None) -> tuple[Guest, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str) or not value:
        raise ValueError("Scenario guests must be a nonempty list")
    guests = tuple(parse_guest(_cast(item, cards)) for item in value)
    unique_ids(guests, "guest")
    late = [item["id"] for item in guests if item["arrives_at"] >= closes_at]
    if late:
        raise ValueError(f"Guests must arrive before closing time: {', '.join(late)}")
    return guests


def _staff(value: Any, guests: Sequence[Guest], cards: Mapping[str, Card] | None) -> tuple[StaffMember, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError("Scenario staff must be a list")
    staff = tuple(parse_staff_member(_cast(item, cards)) for item in value)
    unique_ids([*guests, *staff], "guests and staff")
    return staff


def _cast(entry: Any, cards: Mapping[str, Card] | None) -> Any:
    # A scenario names a guest's card by ID; the guest record carries the card itself.
    if not isinstance(entry, Mapping) or "card" not in entry:
        return entry
    if "traits" in entry or not isinstance(entry["card"], str):
        raise ValueError("A guest cast from a card names the card by ID instead of listing traits")
    rest = {key: value for key, value in entry.items() if key != "card"}
    if cards is None:
        return {**rest, "traits": {}}
    if entry["card"] not in cards:
        raise ValueError(f"Unknown character card {entry['card']!r}")
    card = cards[entry["card"]]
    return {**rest, "traits": dict(card["params"]), "card": card}


def _with_ties(guests: Sequence[Guest], ties: Sequence[Tie]) -> tuple[Guest, ...]:
    # Only guests with ties carry the field, so guests without any keep their plain shape.
    names = {item["id"]: item["name"] for item in guests}
    held = {item["id"]: own_ties(item["id"], ties, names) for item in guests}
    return tuple(Guest(**item, ties=held[item["id"]]) if held[item["id"]] else item for item in guests)


def open_evening(room: Mapping[str, Any], scenario: Scenario, seed: int) -> World:
    """Open the inn for a scenario's evening.

    Args:
        room: Room definition. Its own `actors` and `arrival` sections are not used: the
            scenario says who comes tonight and how they arrive.
        scenario: Validated scenario.
        seed: Seed of tonight's arrival needs and decision policy.
    Returns:
        New world in which the guests due at opening have come in, as far as the door's free
        spots allow, and the others are expected in order of arrival.
    Raises:
        ValueError: The room is invalid or has no door for guests to come in by.
    """
    world = create_world({key: value for key, value in room.items() if key not in ("actors", "arrival")}, seed)
    if not any(item["kind"] == "door" for item in world["map"]["objects"]):
        raise ValueError("A scenario needs a door for its guests to come in by")
    # The news is drawn from a stream of its own, so tonight's needs and the opening order stay as they were.
    news = scenario.news if scenario.news_tonight is None else draw_news(
        scenario.news, scenario.news_tonight, Random(f"{seed}:news"))
    world.update({"expected": _expected(scenario, seed), "closes_at": scenario.closes_at,
                  "last_call_at": scenario.last_call_at, "news": [News(**item) for item in news]})
    take_posts(world, scenario.staff)
    admit_arrivals(world)
    return world


def _expected(scenario: Scenario, seed: int) -> list[ExpectedGuest]:
    # Tonight's needs are drawn at opening, in listed order, so the evening replays from its seed.
    # Sorting is stable: guests due at the same moment keep their listed order at the door.
    drawn = [cast(ExpectedGuest, deepcopy(item)) for item in arriving(scenario.guests, scenario.arrival, seed)]
    # Guests due at opening take the window's moments, evenly spaced, in an order drawn by a stream of
    # their own so the needs above stay as they were; with no window they keep their time of 0.
    opening = [item for item in drawn if item["arrives_at"] == 0]
    if scenario.opening_window and opening:
        first, last = scenario.opening_window
        Random(f"{seed}:opening").shuffle(opening)
        for place, item in enumerate(opening):
            item["arrives_at"] = first + (last - first) * place / max(len(opening) - 1, 1)
    if scenario.ailing_fatigue is not None:
        # The unwell guest is drawn from a stream of their own too, and only their tiredness changes.
        sick = draw_ailing(scenario.guests, Random(f"{seed}:ailment"))
        for item in drawn:
            if item["id"] == sick:
                item["ailing"] = True
                item["needs"]["fatigue"] = scenario.ailing_fatigue
    return sorted(drawn, key=lambda item: item["arrives_at"])


def check_saved_expected(world: Mapping[str, Any]) -> None:
    """Check the guests a saved world still expects.

    Args:
        world: Decoded save with `expected` and `closes_at`.
    Raises:
        ValueError: A guest lacks drawn needs, they are out of order or after closing, or an ID repeats.
    """
    closes_at, expected = world.get("closes_at"), world.get("expected")
    if closes_at is not None:
        number(closes_at, "Saved closing time", 0, math.inf)
    if not isinstance(expected, list):
        raise ValueError("Invalid saved expected guests")
    guests = [_expected_guest(item, world) for item in expected]
    times = [item["arrives_at"] for item in guests]
    if times != sorted(times) or (closes_at is not None and any(time >= closes_at for time in times)):
        raise ValueError("Saved expected guests must arrive in order before closing")
    ids = [item["id"] for item in [*world["actors"], *world["departed"], *guests]]
    if len(set(ids)) != len(ids):
        raise ValueError("Saved visitors need unique IDs")


def _expected_guest(item: Any, world: Mapping[str, Any]) -> Guest:
    if not isinstance(item, dict) or not isinstance(item.get("needs"), dict):
        raise ValueError("Saved expected guest has no drawn needs")
    for need, value in item["needs"].items():
        if need not in world["rules"]["need_rates"]:
            raise ValueError(f"Unknown saved need {need!r}")
        number(value, need, 0, 100)
    if type(item.get("ailing", False)) is not bool:
        raise ValueError("Saved expected guest has a malformed ailing flag")
    return parse_guest({key: value for key, value in item.items() if key not in ("needs", "ailing")})
