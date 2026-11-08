"""The measurements of one headless evening, gathered into the report `make evening` writes."""

from collections.abc import Mapping, Sequence
from typing import Any

from tavern.evening.ailment_metrics import ailment_counts
from tavern.evening.aim_metrics import aim_counts
from tavern.evening.choice_metrics import choice_counts
from tavern.evening.closing_metrics import closing_counts
from tavern.evening.drink_metrics import drink_counts
from tavern.evening.fight_metrics import fight_counts
from tavern.evening.giving_metrics import giving_counts
from tavern.evening.goal_metrics import chased_counts, goal_counts, goal_kind_counts, promise_counts
from tavern.evening.invitation_metrics import invitation_counts
from tavern.evening.lockstep import Evening
from tavern.evening.manner_metrics import manner_counts
from tavern.evening.metrics import (attention_counts, bar_metrics, conversation_counts, dice_metrics, evening_metrics,
                                    intention_counts, news_metrics, sleep_metrics, unspoken_calls, writer_stats)
from tavern.evening.player_metrics import player_counts
from tavern.evening.project_metrics import project_counts
from tavern.evening.recording import Record, Tariff
from tavern.evening.repetition import ALIKE, repetition_counts
from tavern.evening.response_metrics import response_counts
from tavern.evening.speech_metrics import speech_counts, stage_counts
from tavern.evening.story_score import WEIGHTS, story_moments, story_score
from tavern.hall.staff import on_staff
from tavern.hall.state import World


def evening_report(evening: Evening, world: World, calls: Sequence[Record], run: Mapping[str, Any],
                   input_usd_per_million: float, stuck_threshold: float,
                   tariffs: Mapping[str, Tariff], writer_tariff: Tariff) -> dict[str, Any]:
    """Measure a finished headless evening into the report written as metrics.json.

    Args:
        evening: What the lockstep runner logged.
        world: The world the evening ended in.
        calls: The evening's model calls: recorded live, or replayed.
        run: How the evening was invoked; the report carries it first, unchanged.
        input_usd_per_million: USD tariff per million input tokens of kinds without a tariff (Jev's).
        stuck_threshold: Seconds a stall may last before it counts as stuck.
        tariffs: Full tariffs of call kinds priced otherwise than Jev.
        writer_tariff: Tariff of the model that writes the guests' lines.
    Returns:
        The `run` section, then one section per measurement, in the order `metrics.json` shows them.
    """
    player = player_counts(evening.events, None if world["player"] is None else world["player"]["actor_id"])
    names = {item["id"]: item["name"] for item in [*world["actors"], *world["departed"]]}
    return {"run": run,
            **evening_metrics(evening, calls, input_usd_per_million, stuck_threshold, tariffs),
            "intentions": intention_counts(evening), "repetition": repetition_counts(evening.events, ALIKE),
            "choice": choice_counts(evening.choices, evening.events),
            "responses": response_counts(evening.events), "aims": aim_counts(evening.events),
            "projects": project_counts(evening.events), "invitations": invitation_counts(evening.events),
            "goals": goal_counts(evening.events), "goal_kinds": goal_kind_counts(evening.events),
            "chased": chased_counts(evening.events), "promises": promise_counts(evening.events),
            "attention": attention_counts(evening), "conversation": conversation_counts(evening),
            "news": news_metrics(world), "dice": dice_metrics(evening.events),
            "sleep": sleep_metrics(evening.events, world["departed"], world["closes_at"]),
            "drink": drink_counts(evening.events, [*world["actors"], *world["departed"]]),
            "speeches": speech_counts(evening.events), "stage": stage_counts(evening.events),
            "giving": giving_counts(evening.events), "manners": manner_counts(evening.events),
            "closing": closing_counts(world["departed"], world["last_call_at"], world["closes_at"]),
            "ailment": ailment_counts(evening.events, names),
            "fights": fight_counts(world["fights"], evening.events, names),
            "story": story_score(story_moments(evening.events), WEIGHTS),
            "bar": bar_metrics(evening.events, [item["id"] for item in world["actors"] if on_staff(item)]),
            "writer": {**writer_stats(evening, calls, "turn", writer_tariff),
                       "unspoken_calls": unspoken_calls(evening, calls, "turn")},
            **({} if player is None else {"player": player})}
