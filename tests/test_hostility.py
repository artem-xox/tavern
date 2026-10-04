"""Who a guest may shove or fight: only the disliked, after a recent cause, by temper and drink."""

from typing import Any

import pytest

from tavern.social.hostility import hostile_targets
from hostile_view import QUARREL, person, thought, view

DRUNK = 0.5

# Sober guests on good terms, and guests missing any one of the conditions, are never offered the verbs.
PEACEFUL = [
    pytest.param(view(), id="no-cause"),
    pytest.param(view(opinion=-40.0), id="disliked-but-nothing-happened"),
    pytest.param(view(QUARREL, temper=0.3), id="sober-and-calm"),
    pytest.param(view(QUARREL, temper=None), id="no-temper-trait"),
    pytest.param(view(QUARREL, opinion=50.0), id="old-friend-after-a-spat"),
    pytest.param(view(QUARREL, opinion=-9.0), id="opinion-just-above-the-line"),
    pytest.param(view([thought("quarrel", "bea", 130.0)], opinion=-40.0), id="old-cause"),
    pytest.param(view([thought("quarrel", "cid", 30.0)], opinion=-40.0), id="cause-about-someone-else"),
    pytest.param(view([thought("chat", "bea", 30.0)], opinion=-40.0), id="pleasant-thought-is-no-cause"),
    pytest.param(view(QUARREL, opinion=-40.0, people=[]), id="nobody-in-sight"),
    pytest.param(view(QUARREL, opinion=-40.0, people=[person("bea", table_id="far", seat_id="fw")]),
                 id="at-another-table"),
    pytest.param(view(QUARREL, opinion=-40.0, people=[person("bea", post="Bar")]), id="the-barkeep"),
    pytest.param(view(QUARREL, opinion=-40.0, people=[person("ada")]), id="oneself"),
]


@pytest.mark.parametrize("verb", [pytest.param("shove", id="shove"), pytest.param("start_fight", id="start-fight")])
@pytest.mark.parametrize("observation", PEACEFUL)
def test_peaceful_guests_get_no_hostile_targets(observation: dict[str, Any], verb: str) -> None:
    assert hostile_targets(observation, verb) == []


@pytest.mark.parametrize("observation, shove, fight", [
    pytest.param(view(QUARREL, opinion=-40.0), ["bea"], [], id="sober-hothead-shoves-but-does-not-fight"),
    pytest.param(view(QUARREL, opinion=-10.0), ["bea"], [], id="opinion-exactly-at-the-line"),
    pytest.param(view(QUARREL, opinion=-40.0, temper=1.0), ["bea"], ["bea"], id="sober-furious-guest-fights"),
    pytest.param(view(QUARREL, opinion=-40.0, drunkenness=DRUNK), ["bea"], ["bea"], id="drink-loosens-restraint"),
    pytest.param(view(QUARREL, opinion=-40.0, temper=0.3, drunkenness=DRUNK), ["bea"], [], id="drunk-and-calm"),
    pytest.param(view([thought("insulted", "bea", 30.0)], opinion=-30.0), ["bea"], [], id="insult-is-a-cause"),
    pytest.param(view([thought("seat_taken", "bea", 100.0)], opinion=-40.0), ["bea"], [], id="seat-taken-is-a-cause"),
    pytest.param(view([thought("line_cut", "bea", 5.0)], opinion=-40.0), ["bea"], [], id="line-cut-is-a-cause"),
    pytest.param(view([thought("friend_insulted", "bea", 119.0)], opinion=-40.0), ["bea"], [],
                 id="friend-insulted-is-a-cause"),
    pytest.param(view(QUARREL, opinion=-40.0, people=[person("bea", table_id=None, seat_id=None, beside=True)]),
                 ["bea"], [], id="standing-beside-her"),
    pytest.param(view(QUARREL, opinion=-40.0, people=[person("bea"), person("bea")]), ["bea"], [],
                 id="listed-twice-offered-once"),
])
def test_the_disliked_after_a_recent_cause_are_hostile_targets(observation: dict[str, Any], shove: list[str],
                                                               fight: list[str]) -> None:
    assert (hostile_targets(observation, "shove"), hostile_targets(observation, "start_fight")) == (shove, fight)


def test_targets_come_sorted_by_id() -> None:
    thoughts = [thought("quarrel", name, 30.0) for name in ("dan", "bea")]
    relations = {name: {"name": name.title(), "opinion": -40.0, "familiarity": "acquaintance"} for name in ("bea", "dan")}
    observation = view(thoughts, people=[person("dan"), person("bea")])
    observation["actor"]["relations"] = relations
    assert hostile_targets(observation, "shove") == ["bea", "dan"]


@pytest.mark.parametrize("verb", [pytest.param("talk", id="a-peaceful-verb"), pytest.param("", id="empty")])
def test_only_hostile_verbs_have_targets(verb: str) -> None:
    with pytest.raises(ValueError, match="hostile verb"):
        hostile_targets(view(QUARREL, opinion=-40.0), verb)
