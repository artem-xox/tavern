"""The tunable rules of a new world: rates, timings and thresholds, each with the reason for its number."""

import math

from collections.abc import Mapping
from tavern.body.activities import ACTIVITIES
from tavern.body.expression import EMOTES
from tavern.hall.state import Rules
from tavern.hall.validation import integer, number
from tavern.social.dice import check_dice_rules
from typing import Any


def default_rules() -> Rules:
    """Give a new world the game's tunable rules.

    Returns:
        A fresh set, owned by the caller: every world keeps its own copy in its save. Rates are
        per game second, distances in cells.
    """
    return {"move_seconds": 0.35, "blocked_timeout": 3.0, "vision_radius": 5,
            "need_rates": {"thirst": 0.18, "fatigue": 0.05, "bladder": 0.10,
                           "social": 0.18, "boredom": 0.25},
            "durations": {verb: activity.duration for verb, activity in ACTIVITIES.items()
                          if activity.duration is not None},
            # Seconds a visitor waits in line before reconsidering: base, plus this much per unit
            # of the patience trait and per unit of urgency of the need the place relieves.
            "queue_patience": {"base": 5.0, "patience": 40.0, "urgency": 30.0},
            "queue_needs": {"tap": "thirst", "toilet": "bladder", "darts": "boredom"},
            # Salience at which a visitor glances at a sound, and at which it interrupts them;
            # each wall cell between a sound and a listener multiplies its loudness by wall_damping.
            "attention": {"glance": 0.15, "interrupt": 0.5, "wall_damping": 0.5,
                          "glance_seconds": 2.0, "turn_seconds": 3.0},
            # How long each emote shows; a route blocked for long_wait seconds shows `waiting`.
            "emote_seconds": {"alert": 1.5, "confused": 2.5, "angry": 4.0, "affection": 3.0, "sleep": 5.0,
                              "waiting": 0.5},
            "long_wait": 2.0,
            # A middling drinker's rise per beer, how much wears off each second, and how often a
            # wasted guest at their table nods off, per second.
            "drunkenness": {"per_beer": 0.2, "per_second": 0.0005, "doze_per_second": 0.01},
            # Scenes (`tavern.social.scenes`, `tavern.social.turns`): seconds before the first line and per line
            # at least, how long a scene holds its guests once a closing line is spoken (so it can be heard),
            # reading speed, how long a claimed line may keep the others waiting, social
            # relief per friendly act, the wish for company below which a scene ends, its size, how
            # many cells apart guests may stand to talk, the need that makes a partner decline, and how many
            # lines (`tavern.social.heard`) a guest remembers of tonight's talk.
            "conversation": {"opening": 0.5, "min_gap": 2.5, "linger": 2.0, "chars_per_second": 15.0,
                             "turn_timeout": 10.0,
                             "relief": 25.0, "satisfied": 25.0, "max_participants": 4, "reach": 2,
                             "pressing": 75.0, "recall_lines": 40},
            # News (`tavern.social.facts`): how far a listener believes what a teller says, by how well they
            # know the teller (friends are believed most), and the share of that belief kept by a guest who only
            # overheard it.
            "news": {"trust": {"friend": 0.9, "acquaintance": 0.75, "stranger": 0.6}, "overheard": 0.5},
            # Dice (`tavern.social.dice`): a player's form is the weighted traits less drunkenness times `drink`;
            # half the gap in form (`edge`) moves the first player's chance off 0.5, kept within `odds` so
            # luck always counts. A game takes game_seconds once two sit; a lone player waits wait_seconds.
            "dice": {"skill": {"patience": 0.4, "curiosity": 0.3, "courage": 0.3}, "drink": 0.6, "edge": 0.5,
                     "odds": [0.2, 0.8], "game_seconds": 25.0, "wait_seconds": 30.0},
            # Bartending (`tavern.body.bartending`): a barkeep leaves a guest alone for this many seconds after
            # hearing them speak, so he is neither silent nor a bore at the bar.
            "bartending": {"chat_gap": 60.0},
            # Giving (`tavern.social.giving`): a receiver turns a gift down when their opinion of the giver is
            # below refuse_below (a grudge, not mere dislike), and the same gift is not repeated, nor passed
            # back, within again_after seconds, so two guests cannot hand a mug to and fro forever.
            # A host who poured a mug for someone has carry_for seconds to hand it over before the errand lapses.
            "giving": {"refuse_below": -20.0, "again_after": 120.0, "carry_for": 30.0},
            # Manners (`tavern.social.tables`): a hall asks for table manners in its layout (`table_manners`), so
            # that one without tables to speak of, or a test, can do without them.
            "manners": {"table_intrusion": False}}


def check_rules(world: Mapping[str, Any]) -> None:
    """Check the rules saved with a world.

    Args:
        world: Decoded save whose `rules` must match `default_rules` in shape: positive rates, one
            duration per timed verb, all needs, and ordered attention thresholds.
    Raises:
        ValueError: A rule is missing, unknown or out of range.
    """
    rules = world["rules"]
    values = [rules["move_seconds"], rules["blocked_timeout"],
              *rules["durations"].values(), *rules["need_rates"].values()]
    if any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("Invalid saved simulation rates")
    if type(rules["vision_radius"]) is not int or not 0 <= rules["vision_radius"] <= 100:
        raise ValueError("Invalid saved vision radius")
    if set(rules["durations"]) != {verb for verb, activity in ACTIVITIES.items() if activity.duration is not None}:
        raise ValueError("Invalid saved action definitions")
    if set(rules["need_rates"]) != {"thirst", "fatigue", "bladder", "social", "boredom"}:
        raise ValueError("Invalid saved needs")
    patience = rules["queue_patience"]
    if set(patience) != {"base", "patience", "urgency"}:
        raise ValueError("Invalid saved patience in line")
    for value in patience.values():
        number(value, "Saved patience in line", 0, math.inf)
    if not isinstance(rules["queue_needs"], dict) or not set(rules["queue_needs"].values()) <= set(rules["need_rates"]):
        raise ValueError("Invalid saved needs behind lines")
    _validate_attention_rules(rules.get("attention"))
    lifetimes = rules.get("emote_seconds")
    if not isinstance(lifetimes, dict) or set(lifetimes) != set(EMOTES):
        raise ValueError("Invalid saved emote lifetimes")
    for value in [*lifetimes.values(), rules.get("long_wait")]:
        number(value, "Saved emote time", 0, math.inf)
    _validate_conversation_rules(rules.get("conversation"))
    _validate_news_rules(rules.get("news"))
    check_dice_rules(rules.get("dice"))
    _validate_bartending_rules(rules.get("bartending"))
    _validate_giving_rules(rules.get("giving"))
    _validate_manners_rules(rules.get("manners"))


def _validate_manners_rules(manners: Any) -> None:
    if not isinstance(manners, dict) or set(manners) != {"table_intrusion"} or type(manners["table_intrusion"]) is not bool:
        raise ValueError("Invalid saved manners rules")


def _validate_giving_rules(giving: Any) -> None:
    if not isinstance(giving, dict) or set(giving) != {"refuse_below", "again_after", "carry_for"}:
        raise ValueError("Invalid saved giving rules")
    number(giving["refuse_below"], "Saved giving refusal threshold", -100, 100)
    number(giving["again_after"], "Saved giving wait", 0, math.inf)
    if not 0 < number(giving["carry_for"], "Saved giving carry time", 0, math.inf):
        raise ValueError("A saved giving carry time must be positive")


def _validate_bartending_rules(bartending: Any) -> None:
    if not isinstance(bartending, dict) or set(bartending) != {"chat_gap"}:
        raise ValueError("Invalid saved bartending rules")
    if not 0 < number(bartending["chat_gap"], "Saved chat gap", 0, math.inf):
        raise ValueError("A saved chat gap must be positive")


def _validate_news_rules(news: Any) -> None:
    if not isinstance(news, dict) or set(news) != {"trust", "overheard"}:
        raise ValueError("Invalid saved news rules")
    trust = news["trust"]
    if not isinstance(trust, dict) or set(trust) != {"friend", "acquaintance", "stranger"}:
        raise ValueError("Saved news trust must cover friends, acquaintances and strangers")
    for value in [*trust.values(), news["overheard"]]:
        # A belief of nothing would make a copy worthless, so each share is above zero.
        if not 0 < number(value, "Saved news rule", 0, 1):
            raise ValueError("Saved news rules must be above zero")


def _validate_conversation_rules(conversation: Any) -> None:
    keys = {"opening", "min_gap", "linger", "chars_per_second", "turn_timeout", "relief", "satisfied", "max_participants",
            "reach", "pressing", "recall_lines"}
    if not isinstance(conversation, dict) or set(conversation) != keys:
        raise ValueError("Invalid saved conversation rules")
    for key in keys:
        number(conversation[key], f"Saved conversation rule {key}", 0, math.inf)
    if conversation["linger"] > conversation["min_gap"]:
        raise ValueError("Saved conversations would speak again before a closing line was heard out")
    if conversation["chars_per_second"] <= 0 or conversation["max_participants"] < 2:
        raise ValueError("Saved conversations could never be read or held")
    integer(conversation["recall_lines"], "Saved conversation rule recall_lines", 1, 1000)


def _validate_attention_rules(attention: Any) -> None:
    keys = {"glance", "interrupt", "wall_damping", "glance_seconds", "turn_seconds"}
    if not isinstance(attention, dict) or set(attention) != keys:
        raise ValueError("Invalid saved attention rules")
    for key in keys:
        number(attention[key], f"Saved attention rule {key}", 0, math.inf)
    if not 0 < attention["glance"] <= attention["interrupt"] or attention["wall_damping"] > 1:
        raise ValueError("Saved attention thresholds are out of order")
