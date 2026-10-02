"""The verbs visitors perform: targets, timing, effects, and how people and models name them."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from tavern.conversation import complete_conversation
from tavern.hearing import Sound
from tavern.memory import grieve, record_event

# An effect receives the world, the visitor, and the target: an object, a partner, or None.
Effect = Callable[[Mapping[str, Any], dict[str, Any], dict[str, Any] | None], None]


@dataclass(frozen=True)
class Activity:
    """One verb: what it needs, how long it takes, what it changes, and how it is described.

    Attributes:
        verb: Action verb used in actions, events, and saved worlds.
        target_kinds: Object kinds it can target; empty for verbs without an object target.
        partner: Whether it targets another visitor instead of an object.
        duration: Seconds of interaction, or None for a decision step that never runs in the world.
        requires_item: Inventory item the visitor must hold to start.
        empty_target: Refusal when the target has no stock left, or None when stock does not matter.
        leaves_seat: Whether starting it gives up the visitor's seat even without walking away.
        needs: Changes to needs on completion, clamped to 0–100.
        effect: Further consequences on completion.
        on_arrival: Called when the visitor reaches the target, before the interaction runs.
        label: Command name in the inspector.
        status: Short status shown under the visitor, or None to show the verb.
        pose: Character pose while interacting, or None for the resting pose.
        doing: How others see someone doing it, in the briefing.
        done: How a visitor remembers having done it, in the briefing.
        what: Wording for the evaluator; `{target}` stands for the quoted target ID.
        guidance: When the evaluator should consider it natural.
        interruptible: Whether a loud enough stimulus stops it; otherwise the visitor finishes first.
        sound: What others hear when the interaction begins, or None for a silent activity.
    """

    verb: str
    what: str
    guidance: str
    duration: float | None
    target_kinds: tuple[str, ...] = ()
    partner: bool = False
    requires_item: str | None = None
    empty_target: str | None = None
    leaves_seat: bool = False
    needs: Mapping[str, float] = field(default_factory=lambda: MappingProxyType({}))
    effect: Effect | None = None
    on_arrival: Effect | None = None
    label: str | None = None
    status: str | None = None
    pose: str | None = None
    doing: str | None = None
    done: str | None = None
    interruptible: bool = False
    sound: Sound | None = None


def _pour(world: Mapping[str, Any], actor: dict[str, Any], tap: dict[str, Any] | None) -> None:
    tap["stock"] -= 1
    actor["inventory"]["beer"] += 1


def _drink(world: Mapping[str, Any], actor: dict[str, Any], target: dict[str, Any] | None) -> None:
    actor["inventory"]["beer"] -= 1
    actor["visit"]["beers"] += 1


def _chat(world: Mapping[str, Any], actor: dict[str, Any], partner: dict[str, Any] | None) -> None:
    complete_conversation(world, actor, partner)


def _go_home(world: Mapping[str, Any], actor: dict[str, Any], door: dict[str, Any] | None) -> None:
    # step_world moves the visitor out once every actor has finished this tick.
    actor["visit"]["left_at"] = world["time"]


def _settle(world: Mapping[str, Any], actor: dict[str, Any], seat: dict[str, Any] | None) -> None:
    # The chair a visitor sits down on becomes their own; taking someone else's own seat wrongs them.
    if actor["seat_id"] != seat["id"]:
        for owner in world["actors"]:
            if owner["id"] != actor["id"] and owner["favorite_seat_id"] == seat["id"]:
                grieve(owner, f"{actor['name']} took my seat ({seat['name']})")
                record_event(world, owner, "seat_taken", f"{actor['name']} took {owner['name']}'s seat ({seat['name']})")
    actor.update(seat_id=seat["id"], favorite_seat_id=seat["id"])


ACTIVITIES: Mapping[str, Activity] = MappingProxyType({activity.verb: activity for activity in (
    Activity(verb="take_beer", target_kinds=("tap",), duration=0.8, empty_target="Beer tap is empty",
             leaves_seat=True, effect=_pour, label="Get a beer", status="getting ale", pose="TakeBeer",
             doing="fetching ale", done="poured a mug of ale",
             what="walk to the tap {target} and pour a mug of ale to carry",
             guidance="Thirsty guests and newcomers naturally fetch a drink. It is pointless while they already "
                      "hold a mug, or when the tap has run dry."),
    Activity(verb="drink", duration=3.0, requires_item="beer",
             needs=MappingProxyType({"thirst": -60, "bladder": 25}), effect=_drink, label="Drink beer", interruptible=True,
             status="sipping ale", pose="Drinking", doing="drinking", done="drank a beer",
             what="drink the mug of ale they are holding",
             guidance="Sipping ale at the table is the heart of a tavern evening; it quenches thirst but fills "
                      "the bladder."),
    Activity(verb="rest", target_kinds=("chair",), duration=3.0, needs=MappingProxyType({"fatigue": -65}),
             label="Rest", pose="Seated", interruptible=True, doing="resting", done="rested",
             what="rest on the chair {target}",
             guidance="It eases tiredness."),
    Activity(verb="sit", target_kinds=("chair",), duration=14.0, needs=MappingProxyType({"fatigue": -65}),
             on_arrival=_settle, label="Sit at a table", status="seated", pose="Seated",
             interruptible=True,
             doing="heading to a seat", done="sat a while",
             what="sit in their own seat {target} for a while",
             guidance="Sitting in their own seat is a guest's natural resting state: it eases tiredness, it is "
                      "where they sip their ale, and it lets them chat with whoever shares the table. Getting "
                      "up needs a reason."),
    Activity(verb="talk", partner=True, duration=8.0, effect=_chat, label="Chat with a neighbor",
             status="chatting", pose="Talking",
             sound=Sound("chat", 0.25, 6.0, "a conversation"), doing="talking", done="chatted",
             what="chat with {target}, who sits at their table",
             guidance="It eases the wish for company of both and lets them share where the beer, WC and darts "
                      "are. After a few beers an impatient pair may quarrel instead, leaving both aggrieved; "
                      "someone who wronged them tonight is poor company. Right after a chat, with their wish "
                      "for company satisfied, a quiet sip or a rest is more natural than yet another chat."),
    Activity(verb="play_darts", target_kinds=("darts",), duration=10.0, leaves_seat=True,
             needs=MappingProxyType({"boredom": -65}), label="Play darts", status="darts", pose="Darts", interruptible=True,
             sound=Sound("thud", 0.25, 10.0, "darts thudding into the board"),
             doing="playing darts", done="played darts",
             what="play a round of darts at {target}",
             guidance="A lively pastime for a bored guest; it means leaving their seat for a while."),
    Activity(verb="use_toilet", target_kinds=("toilet",), duration=2.0, leaves_seat=True,
             needs=MappingProxyType({"bladder": -65}), label="Use the toilet", status="WC", pose="Bathroom",
             doing="heading to the WC", done="used the WC",
             what="use the WC {target}",
             guidance="Necessary once the bladder presses, pointless before."),
    Activity(verb="inspect", duration=0.8, label="Explore the room", doing="looking around", interruptible=True,
             done="looked around",
             what="explore the room to discover or re-check places",
             guidance="Worthwhile only when something they need has not been found yet; otherwise it is aimless "
                      "wandering."),
    Activity(verb="wait", duration=1.0, label="Wait a little", doing="waiting", interruptible=True, done="waited",
             what="wait a moment and do nothing",
             guidance="Idling where they stand is rarely the most natural thing."),
    Activity(verb="leave", target_kinds=("door",), duration=1.0, effect=_go_home, label="Go home",
             status="going home", doing="heading for the door", done="left",
             what="leave the inn for the night through {target}, ending their visit for good",
             guidance="Going home is the natural end of an evening, not a failure. It is the right move when "
                      "they are content: they have stayed a good while (several minutes of "
                      "`self.visit.seconds`), drunk their fill (two or three beers in `self.visit.beers`) and "
                      "their needs are mostly low, or when their company has gone home and the evening has run "
                      "its course; after a long evening and several beers, a guest left alone in the inn "
                      "naturally heads home. It is also right when the evening has gone wrong: the beer has run "
                      "out (the tap shows stock 0 when last seen) while they are still thirsty, someone took "
                      "their seat, someone offended them or they had a quarrel (see `self.visit.grievances`), "
                      "or their needs keep going unmet. Leaving is a poor choice when they have just arrived, "
                      "still hold an undrunk mug, want a drink that is still available, or are enjoying good "
                      "company. Impatient guests walk out sooner after a grievance; comfort-loving guests "
                      "linger in a cosy seat."),
    # Gazing at the flames or the road outside is a gentler pastime than darts.
    Activity(verb="watch", target_kinds=("window", "fireplace"), duration=8.0,
             needs=MappingProxyType({"boredom": -40}), label="Watch the fire or the view", interruptible=True,
             status="at the window", doing="admiring the view", done="admired the view",
             what="stand by {target} and watch it for a while",
             guidance="Gazing into the flames of the fireplace or out of a window at the road is a quiet "
                      "pleasure that eases boredom more gently than darts. Comfort-loving guests especially "
                      "enjoy the warmth of the fire, curious ones the view outside. It means leaving their seat "
                      "for a while."),
    # A decision step, not a world action: a second evaluation picks the chair to `sit` on.
    Activity(verb="seating", duration=None,
             what="find a seat: choose a free chair at one of the tables and sit down",
             guidance="A separate decision picks the chair, which becomes their own seat for the rest of the "
                      "visit. Visitors who have just come in usually want to sit down and have a beer first. If "
                      "they already have a seat of their own, this means moving to another table, which is "
                      "worth it mainly to join company when they feel lonely."),
)})


def client_activities(activities: Mapping[str, Activity]) -> dict[str, dict[str, Any]]:
    """Describe the verbs the world runs, for the browser client.

    Args:
        activities: Activity table.
    Returns:
        Per world verb: command label, status text, pose, target kinds, and whether it
        targets another visitor. Decision steps such as `seating` are left out.
    """
    return {verb: {"label": activity.label, "status": activity.status, "pose": activity.pose,
                   "target_kinds": list(activity.target_kinds), "partner": activity.partner}
            for verb, activity in activities.items() if activity.duration is not None}
