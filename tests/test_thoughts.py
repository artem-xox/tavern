"""Thoughts, mood and opinions: stacking, expiry, opinions per pair, and starting relationships."""

from typing import Any

import pytest

from tavern.thoughts import (THOUGHTS, active_thoughts, familiarity_of, forget_expired, friends_of, mood,
                             opinion_of, seed_relations, think)


def guest(actor_id: str, **needs: float) -> dict[str, Any]:
    """Build a calm visitor with no thoughts or relationships yet."""
    calm = {"thirst": 10, "fatigue": 10, "bladder": 10, "social": 10, "boredom": 10}
    return {"id": actor_id, "name": actor_id.capitalize(), "needs": {**calm, **needs},
            "visit": {"seconds": 0.0, "beers": 0, "grievances": []}, "thoughts": [], "relations": {}}


def wrong(victim: dict[str, Any], kind: str, culprit: dict[str, Any], now: float = 0.0) -> None:
    """Give the victim a thought about the culprit."""
    think(victim, kind, now, f"{culprit['name']} did it ({kind})", f"{culprit['name']} {kind}", about=culprit)


SEAT, CUT, QUARREL, CHAT = (THOUGHTS[kind] for kind in ("seat_taken", "line_cut", "quarrel", "chat"))


@pytest.mark.parametrize("repeats, counted", [
    pytest.param(0, 0, id="empty"),
    pytest.param(1, 1, id="single"),
    pytest.param(SEAT.stack, SEAT.stack, id="up-to-the-cap"),
    pytest.param(SEAT.stack + 2, SEAT.stack, id="duplicates-beyond-the-cap-are-capped"),
])
def test_repeated_wrongs_by_one_person_stack_up_to_a_cap(repeats: int, counted: int) -> None:
    ada, bea = guest("ada"), guest("bea")
    for second in range(repeats):
        wrong(ada, "seat_taken", bea, now=float(second))
    assert (len(active_thoughts(ada["thoughts"], repeats)), mood(ada, repeats), opinion_of(ada, "bea", repeats)) == (
        counted, pytest.approx(counted * SEAT.mood), pytest.approx(counted * SEAT.opinion))


def test_a_capped_repeat_refreshes_the_oldest_instead() -> None:
    ada, bea = guest("ada"), guest("bea")
    for second in range(SEAT.stack + 1):
        wrong(ada, "seat_taken", bea, now=float(second))
    expiries = sorted(thought["expires_at"] for thought in ada["thoughts"])
    assert expiries == [second + SEAT.seconds for second in range(1, SEAT.stack + 1)]


def test_the_cap_is_per_person_and_kind() -> None:
    ada, bea, cid = guest("ada"), guest("bea"), guest("cid")
    for _ in range(SEAT.stack):
        wrong(ada, "seat_taken", bea)
        wrong(ada, "seat_taken", cid)
        wrong(ada, "line_cut", bea)
    assert len(active_thoughts(ada["thoughts"], 0.0)) == 3 * SEAT.stack


@pytest.mark.parametrize("later, counts", [
    pytest.param(0.0, True, id="fresh"),
    pytest.param(SEAT.seconds - 0.1, True, id="just-before-expiry"),
    pytest.param(SEAT.seconds, False, id="expired-at-its-time"),
    pytest.param(SEAT.seconds + 60, False, id="long-expired"),
])
def test_an_expired_thought_stops_counting(later: float, counts: bool) -> None:
    ada, bea = guest("ada"), guest("bea")
    wrong(ada, "seat_taken", bea)
    assert (mood(ada, later), opinion_of(ada, "bea", later)) == (
        (SEAT.mood, SEAT.opinion) if counts else (0.0, 0.0))


@pytest.mark.parametrize("base, kinds, expected", [
    pytest.param(0.0, [], 0.0, id="stranger-with-no-thoughts"),
    pytest.param(30.0, [], 30.0, id="base-opinion-alone"),
    pytest.param(30.0, ["quarrel"], 30.0 + QUARREL.opinion, id="base-plus-a-thought"),
    pytest.param(0.0, ["chat", "quarrel"], CHAT.opinion + QUARREL.opinion, id="good-and-bad-add-up"),
    pytest.param(-95.0, ["quarrel", "quarrel"], -100.0, id="clamped-at-minus-100"),
    pytest.param(95.0, ["chat", "chat"], 100.0, id="clamped-at-100"),
])
def test_opinion_is_the_base_plus_active_thoughts(base: float, kinds: list[str], expected: float) -> None:
    ada, bea = guest("ada"), guest("bea")
    ada["relations"]["bea"] = {"name": "Bea", "opinion": base, "familiarity": "acquaintance"}
    for kind in kinds:
        wrong(ada, kind, bea)
    assert opinion_of(ada, "bea", 1.0) == pytest.approx(expected)


def test_opinions_are_kept_per_ordered_pair() -> None:
    ada, bea = guest("ada"), guest("bea")
    wrong(ada, "seat_taken", bea)
    assert (opinion_of(ada, "bea", 1.0), opinion_of(bea, "ada", 1.0)) == (SEAT.opinion, 0.0)


@pytest.mark.parametrize("start, kind, expected", [
    pytest.param(None, "line_cut", "stranger", id="a-stranger-cutting-in-stays-a-stranger"),
    pytest.param(None, "chat", "acquaintance", id="a-chat-acquaints"),
    pytest.param(None, "quarrel", "acquaintance", id="a-quarrel-acquaints-too"),
    pytest.param("friend", "quarrel", "friend", id="friends-stay-friends"),
])
def test_talking_makes_strangers_acquainted(start: str | None, kind: str, expected: str) -> None:
    ada, bea = guest("ada"), guest("bea")
    if start:
        ada["relations"]["bea"] = {"name": "Bea", "opinion": 50.0, "familiarity": start}
    wrong(ada, kind, bea)
    assert familiarity_of(ada, "bea") == expected


def test_mood_adds_pressing_needs_to_thoughts() -> None:
    calm, parched = guest("ada"), guest("ada", thirst=100, bladder=100)
    assert (mood(calm, 0.0), mood(parched, 0.0) < 0) == (0.0, True)


@pytest.mark.parametrize("kinds, expected", [
    pytest.param([], [], id="empty"),
    pytest.param(["chat"], [], id="pleasant-thoughts-are-no-grievance"),
    pytest.param(["seat_taken"], ["Bea did it (seat_taken)"], id="single"),
    pytest.param(["line_cut", "line_cut"], ["Bea did it (line_cut)"] * 2, id="duplicates-listed-each"),
    pytest.param(["line_cut"] * 3 + ["seat_taken"] * 3, ["Bea did it (line_cut)"] * 2 + ["Bea did it (seat_taken)"] * 3,
                 id="latest-five"),
])
def test_grievances_list_the_active_bad_thoughts(kinds: list[str], expected: list[str]) -> None:
    ada, bea = guest("ada"), guest("bea")
    for kind in kinds:
        wrong(ada, kind, bea)
    assert ada["visit"]["grievances"] == expected


def test_forgetting_drops_expired_thoughts_and_their_grievances() -> None:
    ada, bea = guest("ada"), guest("bea")
    wrong(ada, "line_cut", bea)
    wrong(ada, "seat_taken", bea, now=100.0)
    forget_expired({"time": CUT.seconds + 1, "actors": [ada]})
    assert ([thought["kind"] for thought in ada["thoughts"]], ada["visit"]["grievances"]) == (
        ["seat_taken"], ["Bea did it (seat_taken)"])


def test_a_thought_keeps_its_cause() -> None:
    ada, bea = guest("ada"), guest("bea")
    think(ada, "seat_taken", 5.0, "Bea took my seat", "Bea took Ada's seat (Table · west)", about=bea)
    assert ada["thoughts"] == [{"kind": "seat_taken", "about": "bea", "text": "Bea took my seat",
                                "mood": SEAT.mood, "opinion": SEAT.opinion, "expires_at": 5.0 + SEAT.seconds,
                                "source_event": "Bea took Ada's seat (Table · west)"}]


def test_unknown_thought_kind_fails_loudly() -> None:
    with pytest.raises(ValueError):
        think(guest("ada"), "envy", 0.0, "Bea has a nicer hat", "Bea arrived", about=guest("bea"))


NAMES = {"ada": "Ada", "bea": "Bea", "cid": "Cid"}


@pytest.mark.parametrize("pairs, expected", [
    pytest.param([], {}, id="empty"),
    pytest.param([{"a": "ada", "b": "bea", "kind": "old friends"}],
                 {"ada": {"bea": {"name": "Bea", "opinion": 50.0, "familiarity": "friend"}},
                  "bea": {"ada": {"name": "Ada", "opinion": 50.0, "familiarity": "friend"}}}, id="single-old-friends"),
    pytest.param([{"a": "ada", "b": "bea", "kind": "rivals"}, {"a": "bea", "b": "cid", "kind": "old friends"}],
                 {"ada": {"bea": {"name": "Bea", "opinion": -40.0, "familiarity": "acquaintance"}},
                  "bea": {"ada": {"name": "Ada", "opinion": -40.0, "familiarity": "acquaintance"},
                          "cid": {"name": "Cid", "opinion": 50.0, "familiarity": "friend"}},
                  "cid": {"bea": {"name": "Bea", "opinion": 50.0, "familiarity": "friend"}}}, id="rivals-and-friends"),
])
def test_starting_relationships_seed_both_directions(pairs: list[dict[str, str]], expected: dict[str, Any]) -> None:
    assert seed_relations(pairs, NAMES) == expected


@pytest.mark.parametrize("pairs", [
    pytest.param([{"a": "ada", "b": "bea", "kind": "lovers"}], id="unknown-kind"),
    pytest.param([{"a": "ada", "b": "ada", "kind": "rivals"}], id="with-oneself"),
    pytest.param([{"a": "ada", "b": "zed", "kind": "rivals"}], id="unknown-guest"),
    pytest.param([{"a": "ada", "kind": "rivals"}], id="malformed-pair"),
    pytest.param([{"a": "ada", "b": "bea", "kind": "rivals"}, {"a": "bea", "b": "ada", "kind": "old friends"}],
                 id="duplicate-pair"),
])
def test_malformed_starting_relationships_fail_loudly(pairs: list[dict[str, str]]) -> None:
    with pytest.raises(ValueError):
        seed_relations(pairs, NAMES)


@pytest.mark.parametrize("relations, expected", [
    pytest.param({}, [], id="empty"),
    pytest.param({"bea": {"name": "Bea", "opinion": 50.0, "familiarity": "friend"}}, ["bea"], id="single-friend"),
    pytest.param({"bea": {"name": "Bea", "opinion": 80.0, "familiarity": "acquaintance"},
                  "cid": {"name": "Cid", "opinion": 0.0, "familiarity": "friend"}}, ["cid"],
                 id="liking-alone-makes-no-friend"),
])
def test_friends_are_the_people_one_counts_as_friends(relations: dict[str, Any], expected: list[str]) -> None:
    ada = guest("ada")
    ada["relations"] = relations
    assert friends_of(ada) == expected
