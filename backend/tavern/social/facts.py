"""News and the copies guests carry of it: the scenario's items, who starts holding them, and saved copies."""

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

from tavern.hall.validation import number, unique_ids

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
