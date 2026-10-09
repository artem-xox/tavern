"""News and guests' copies of it: the scenario's items, who holds them, how they read, and saved copies."""

from collections.abc import Mapping, Sequence
from random import Random
from typing import Any, TypedDict

from tavern.hall.memory import log_event
from tavern.hall.state import Actor, World
from tavern.hall.validation import number, unique_ids
from tavern.social.names import called
from tavern.social.scenes import Conversation, Turn
from tavern.social.thoughts import familiarity_of

MAX_TEXT = 200  # Characters of a news item: a few sentences a guest could tell in one or two lines.


class News(TypedDict):
    """A news item of tonight's scenario: its `topic`, the original `text`, and `known_by` guest IDs."""

    id: str
    topic: str
    text: str
    known_by: list[str]


class Fact(TypedDict):
    """One guest's copy of a news item.

    `told_as` is the words they heard it in (the original for a first holder), `heard_from` the guest
    who told it (None for a first holder), `heard_at` the game time, `confidence` how far they believe
    it (0–1), `hops` the tellings between the original holders and them, and `overheard` whether they
    caught it from a conversation they were not in.
    """

    topic: str
    told_as: str
    heard_from: str | None
    heard_at: float
    confidence: float
    hops: int
    overheard: bool


class Carried(TypedDict):
    """A copy as its holder's writer sees it: `heard_from` is the teller as the holder calls them (None
    for a first holder). Only the holder's own words (`told_as`) are shown, never the original."""

    id: str
    topic: str
    told_as: str
    heard_from: str | None
    confidence: float


class Inspected(TypedDict):
    """A copy as the inspector shows it: the teller by name (None for a first holder), and the `chain` of
    names from the holder back through each teller to the word "start"."""

    id: str
    topic: str
    told_as: str
    heard_from: str | None
    hops: int
    confidence: float
    overheard: bool
    chain: list[str]


def parse_news(value: Any, guests: Sequence[str]) -> tuple[News, ...]:
    """Validate a scenario's news.

    Args:
        value: List of `{id, topic, text, known_by}` records.
        guests: IDs of tonight's guests.

    Returns:
        The news in listed order. An empty list is allowed: an evening may have none.

    Raises:
        ValueError: The list or an item is malformed, an ID repeats, a text is empty or longer than
            `MAX_TEXT` characters, or `known_by` is empty, repeats a guest or names someone who is
            not a guest (an item nobody holds could never be told).
    """
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError("Scenario news must be a list")
    items = tuple(_item(entry, guests) for entry in value)
    unique_ids(items, "news")
    return items


def _item(data: Any, guests: Sequence[str]) -> News:
    if not isinstance(data, Mapping) or set(data) != {"id", "topic", "text", "known_by"}:
        raise ValueError("A news item has exactly id, topic, text and known_by")
    for key in ("id", "topic", "text"):
        if not isinstance(data[key], str) or not data[key].strip():
            raise ValueError(f"News {key} must be nonempty text, not {data[key]!r}")
    if len(data["text"]) > MAX_TEXT:
        raise ValueError(f"News {data['id']!r} is over {MAX_TEXT} characters")
    holders = data["known_by"]
    if not isinstance(holders, Sequence) or isinstance(holders, str) or not holders:
        raise ValueError(f"News {data['id']!r} must be known by at least one guest")
    if len(set(holders)) != len(holders) or any(holder not in guests for holder in holders):
        raise ValueError(f"News {data['id']!r} must be known by distinct guests of tonight, not {list(holders)!r}")
    return News(id=data["id"], topic=data["topic"], text=data["text"], known_by=list(holders))


def draw_news(news: Sequence[News], count: int, rng: Random) -> tuple[News, ...]:
    """Pick the news told tonight, each item with a single holder.

    Args:
        news: The scenario's items, each with the guests who may know it in `known_by`.
        count: How many items are told, from 1 to `len(news)`.
        rng: Source of the draw; the same seeded stream gives the same news and holders.

    Returns:
        `count` items in their listed order, each copied with `known_by` narrowed to one guest drawn from its
        own list (guests are drawn item by item in listed order, so the order is part of the result).

    Raises:
        ValueError: `count` is below 1 or above the number of items.
    """
    if not 1 <= count <= len(news):
        raise ValueError(f"Tonight's news must be between 1 and {len(news)} items, not {count}")
    return tuple(News(id=news[index]["id"], topic=news[index]["topic"], text=news[index]["text"],
                      known_by=[rng.choice(news[index]["known_by"])])
                 for index in sorted(rng.sample(range(len(news)), count)))


def starting_facts(news: Sequence[News], guest_id: str, now: float) -> dict[str, Fact]:
    """Give a guest who comes in the copies of the news they are listed for.

    Args:
        news: Tonight's originals.
        guest_id: The guest.
        now: Game time of their arrival.

    Returns:
        A copy per item that lists the guest, in the order of `news`: the original text, no teller,
        full confidence, no hops.
    """
    return {item["id"]: Fact(topic=item["topic"], told_as=item["text"], heard_from=None, heard_at=now,
                             confidence=1.0, hops=0, overheard=False)
            for item in news if guest_id in item["known_by"]}


def carried(world: Mapping[str, Any], holder: Mapping[str, Any]) -> list[Carried]:
    """List the news a guest could tell, in their own words.

    Args:
        world: Current world; a teller is looked up among the guests present and gone home.
        holder: The guest.

    Returns:
        Their copies by news ID, with the teller named as the holder calls them (`names.called`).
    """
    people = {item["id"]: item for item in [*world["actors"], *world["departed"]]}
    return [Carried(id=fact_id, topic=copy["topic"], told_as=copy["told_as"], confidence=copy["confidence"],
                    heard_from=None if copy["heard_from"] is None else called(holder, people[copy["heard_from"]]))
            for fact_id, copy in sorted(holder["knowledge"]["facts"].items())]


def inspected(world: Mapping[str, Any], holder: Mapping[str, Any]) -> list[Inspected]:
    """List a guest's copies of the news for the inspector, each with the path it came by.

    Args:
        world: Current world; tellers are looked up among the guests present and gone home.
        holder: The guest.

    Returns:
        Their copies by news ID, with real names (the inspector sees what the guest may not). A chain such
        as ["Brida", "Edda", "start"] reads: Brida heard it from Edda, who knew it from the start.
    """
    people = {item["id"]: item for item in [*world["actors"], *world["departed"]]}
    shown = []
    for fact_id, copy in sorted(holder["knowledge"]["facts"].items()):
        # Saves guarantee each teller holds a copy one hop nearer the start (`check_saved_news`).
        names, step = [holder["name"]], copy
        for _ in range(copy["hops"]):
            teller = people[step["heard_from"]]
            names.append(teller["name"])
            step = teller["knowledge"]["facts"][fact_id]
        shown.append(Inspected(id=fact_id, topic=copy["topic"], told_as=copy["told_as"], hops=copy["hops"],
                               heard_from=None if copy["heard_from"] is None else people[copy["heard_from"]]["name"],
                               confidence=copy["confidence"], overheard=copy["overheard"], chain=[*names, "start"]))
    return shown


def tell(world: World, scene: Conversation, speaker: Actor, addressee: Actor | None) -> None:
    """Give everyone else in the scene who lacks it a copy of the news the last turn told.

    Args:
        world: Current world; `rules.news.trust` says how far each listener believes the teller.
        scene: Speaker's scene, whose last turn carries the `fact_id` told (validated by `turns.check_turn`).
        speaker: Guest telling the news.
        addressee: Unused: a telling is heard by the whole company, whoever it addresses.
    """
    turn = scene["turns"][-1]
    told = speaker["knowledge"]["facts"][turn["fact_id"]]
    heard = []
    for listener in world["actors"]:
        copies = listener["knowledge"]["facts"]
        # A listener who already knows the news keeps the version they first heard.
        if listener["id"] not in scene["participants"] or listener["id"] == speaker["id"] or turn["fact_id"] in copies:
            continue
        trust = world["rules"]["news"]["trust"][familiarity_of(listener, speaker["id"])]
        copies[turn["fact_id"]] = Fact(topic=told["topic"], told_as=turn["line"], heard_from=speaker["id"],
                                       heard_at=world["time"], confidence=told["confidence"] * trust,
                                       hops=told["hops"] + 1, overheard=False)
        heard.append(listener["name"])
    if heard:
        names = heard[0] if len(heard) == 1 else f"{', '.join(heard[:-1])} and {heard[-1]}"
        log_event(world, speaker["id"], "news_told", f"{speaker['name']} told {told['topic']} to {names}")


def overhear(world: World, listener: Actor, speaker: Actor, turn: Turn) -> None:
    """Give a guest outside the scene a copy of news they made out the words of.

    Args:
        world: Current world; `rules.news.overheard` is the share of the teller's confidence they keep.
        listener: Guest who made out the line.
        speaker: Guest who told the news; `turn["fact_id"]` is one of their copies.
        turn: The spoken line, kept as the listener's words. A listener who already knows the news keeps
            their first version.
    """
    copies = listener["knowledge"]["facts"]
    if turn["fact_id"] in copies:
        return
    told = speaker["knowledge"]["facts"][turn["fact_id"]]
    copies[turn["fact_id"]] = Fact(topic=told["topic"], told_as=turn["line"], heard_from=speaker["id"],
                                   heard_at=world["time"],
                                   confidence=told["confidence"] * world["rules"]["news"]["overheard"],
                                   hops=told["hops"] + 1, overheard=True)
    log_event(world, listener["id"], "news_overheard",
              f"{listener['name']} overheard {called(listener, speaker)} tell {told['topic']}")


def check_saved_news(world: Mapping[str, Any]) -> None:
    """Check a saved world's news and every guest's copies of it.

    Args:
        world: Decoded save with `news`, `actors`, `departed` and `expected`.

    Raises:
        ValueError: The news is malformed or held by an unknown guest, or a copy of it is: unknown
            item or topic, empty words, a confidence outside 0–1, hops that do not match the teller,
            a teller who is not a guest, a time outside the evening, or a flag that is not a boolean.
    """
    present = [*world["actors"], *world["departed"]]
    ids = [item["id"] for item in [*present, *world["expected"]]]
    originals = {item["id"]: item for item in parse_news(world.get("news"), ids)}
    tellers = {item["id"] for item in present}
    for guest in present:
        copies = guest["knowledge"].get("facts")
        if not isinstance(copies, dict):
            raise ValueError(f"Saved facts of {guest['id']!r} must be a record")
        for fact_id, copy in copies.items():
            _check_copy(fact_id, copy, originals, tellers, world["time"])
    _check_paths(present)


def _check_paths(guests: Sequence[Mapping[str, Any]]) -> None:
    # Every teller holds the news one hop nearer the start, so a path always leads back (and never loops).
    held = {item["id"]: item["knowledge"]["facts"] for item in guests}
    for guest in guests:
        for fact_id, copy in guest["knowledge"]["facts"].items():
            if copy["heard_from"] is None:
                continue
            told = held[copy["heard_from"]].get(fact_id)
            if told is None or told["hops"] != copy["hops"] - 1:
                raise ValueError(f"Saved copy of news {fact_id!r} of {guest['id']!r} has no path back through "
                                 f"{copy['heard_from']!r}")


def _check_copy(fact_id: str, copy: Any, originals: Mapping[str, News], tellers: set[str], now: float) -> None:
    if fact_id not in originals:
        raise ValueError(f"Saved copy of unknown news {fact_id!r}")
    if not isinstance(copy, dict) or set(copy) != set(Fact.__annotations__):
        raise ValueError(f"Invalid saved copy of news {fact_id!r}")
    if copy["topic"] != originals[fact_id]["topic"]:
        raise ValueError(f"Saved copy of news {fact_id!r} has another topic, {copy['topic']!r}")
    if not isinstance(copy["told_as"], str) or not copy["told_as"].strip():
        raise ValueError(f"Saved copy of news {fact_id!r} has no words")
    if not 0 < number(copy["confidence"], "Saved news confidence", 0, 1):
        raise ValueError(f"Saved copy of news {fact_id!r} is not believed at all")
    number(copy["heard_at"], "Saved news time", 0, now)
    if type(copy["hops"]) is not int or copy["hops"] < 0:
        raise ValueError(f"Saved copy of news {fact_id!r} has invalid hops {copy['hops']!r}")
    if (copy["heard_from"] is None) != (copy["hops"] == 0):
        raise ValueError(f"Saved copy of news {fact_id!r} has a teller exactly when it has hops")
    if copy["heard_from"] is not None and copy["heard_from"] not in tellers:
        raise ValueError(f"Saved copy of news {fact_id!r} was told by an unknown guest {copy['heard_from']!r}")
    if not isinstance(copy["overheard"], bool):
        raise ValueError(f"Saved copy of news {fact_id!r} must say whether it was overheard")
