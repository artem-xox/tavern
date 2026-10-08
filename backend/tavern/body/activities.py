"""The verbs visitors perform: targets, timing, effects, and how people and models name them."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from tavern.body.drunkenness import drink_beer
from tavern.body.hearing import Sound
from tavern.hall.memory import record_event
from tavern.hall.state import Actor, World
from tavern.social.giving import hand_over
from tavern.social.invitations import begin_errand
from tavern.social.names import called
from tavern.social.scenes import join_conversation, start_conversation
from tavern.social.thoughts import think

# An effect receives the world, the visitor, and the target: an object, a partner, or None.
# The target is a place or, for a part in a conversation, the partner.
Effect = Callable[[World, Actor, Any], None]


@dataclass(frozen=True)
class Activity:
    """One verb: what it needs, how long it takes, what it changes, and how it is described.

    Attributes:
        verb: Action verb used in actions, events, and saved worlds.
        target_kinds: Object kinds it can target; empty for verbs without an object target.
        partner: Whether it targets another visitor instead of an object. Such a verb is a part in a
            conversation scene (`tavern.social.scenes`): the scene, not a timer, ends it.
        joins: Whether it joins the partner's scene instead of starting one with them.
        near_person: Whether it targets another visitor at the actor's table or beside them, as a chat does:
            no scene, no walking, and the timer ends it. Shoving and fighting (`tavern.social.hostility`) are
            such verbs.
        names_item: Whether the action names an item from the actor's hands in `Action.item`, as giving does.
        opens_errand: Whether it sends the actor off on an errand for the visitor it targets (see
            `tavern.social.errands`); like giving, it needs that visitor near.
        duration: Seconds of interaction (nominal for a scene part), or None for a decision step
            that never runs in the world.
        family: The `FAMILIES` entry it is chosen under: a first decision picks the family, a
            second the action within it, so requests stay small as verbs and guests grow.
        requires_item: Inventory item the visitor must hold to start.
        empty_target: Refusal when the target has no stock left, or None when stock does not matter.
        shared_target: Whether several visitors may use the target at once, so it is never reserved;
            each takes a spot of their own, and the spots are the target's capacity.
        leaves_seat: Whether starting it gives up the visitor's seat even without walking away.
        game: Whether a game, not this timer, ends it (`tavern.social.dice`); `duration` is only nominal.
        served: Whether, while staff tend a bar (`tavern.hall.staff.tended`), the bar's service, not this timer,
            ends it (`tavern.body.bartending`); `duration` is then only nominal. Without staff the timer does.
        staff_only: Whether only staff do it, and only the bar's own routine starts it: a guest is refused.
        needs: Changes to needs on completion, clamped to 0–100.
        fatigue_per_second: Tiredness gained each second while walking to it or doing it (see `tavern.body.energy`);
            negative when it restores energy.
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
        asleep: Whether the visitor sleeps while doing it: others see a sleeper, and only a loud sound wakes them.
        seated: Whether it can only be done from a seat at a table.
        sound: What others hear when the interaction begins, or None for a silent activity.
    """

    verb: str
    what: str
    guidance: str
    duration: float | None
    family: str
    target_kinds: tuple[str, ...] = ()
    partner: bool = False
    joins: bool = False
    near_person: bool = False
    names_item: bool = False
    opens_errand: bool = False
    requires_item: str | None = None
    empty_target: str | None = None
    shared_target: bool = False
    leaves_seat: bool = False
    game: bool = False
    served: bool = False
    staff_only: bool = False
    needs: Mapping[str, float] = field(default_factory=lambda: MappingProxyType({}))
    fatigue_per_second: float = 0.0
    effect: Effect | None = None
    on_arrival: Effect | None = None
    label: str | None = None
    status: str | None = None
    pose: str | None = None
    doing: str | None = None
    done: str | None = None
    interruptible: bool = False
    asleep: bool = False
    seated: bool = False
    sound: Sound | None = None


def _pour(world: World, actor: Actor, tap: dict[str, Any] | None) -> None:
    if tap is None:
        raise ValueError("Pouring a beer needs a tap")
    tap["stock"] -= 1
    actor["inventory"]["beer"] += 1


def _drink(world: World, actor: Actor, target: dict[str, Any] | None) -> None:
    actor["inventory"]["beer"] -= 1
    actor["visit"]["beers"] += 1
    # Guests without a tolerance trait (cards add it in E10) drink like a middling drinker.
    tolerance = actor["traits"].get("tolerance", 0.5)
    actor["drunkenness"] = drink_beer(actor["drunkenness"], tolerance, world["rules"]["drunkenness"])


def _open_scene(world: World, actor: Actor, partner: Actor | None) -> None:
    if partner is None:
        raise ValueError("Starting a conversation needs a partner")
    start_conversation(world, actor, partner)


def _join_scene(world: World, actor: Actor, member: Actor | None) -> None:
    if member is None:
        raise ValueError("Joining a conversation needs a member to join")
    join_conversation(world, actor, member)


def _confront(world: World, actor: Actor, victim: Actor | None, event: str, thought: str, act: str) -> None:
    # Both remember it, and it is one sound; only the victim holds a grudge for now (E21 resolves the blow).
    if victim is None:
        raise ValueError("A hostile act needs someone to turn on")
    message = f"{actor['name']} {act} {victim['name']}"
    for member in (actor, victim):
        record_event(world, member, event, message)
    think(victim, thought, world["time"], f"{called(victim, actor)} {act} me", message, about=actor)


def _give(world: World, actor: Actor, receiver: Actor | None) -> None:
    action = actor["action"]
    if receiver is None or action is None or action.get("item") is None:
        raise ValueError("Giving needs someone to give to and an item to give")
    hand_over(world, actor, receiver, action["item"])


def _bring_drink(world: World, actor: Actor, receiver: Actor | None) -> None:
    if receiver is None:
        raise ValueError("Bringing a drink needs someone to bring it to")
    begin_errand(world, actor, receiver, "buy_drink", unasked=True)


def _shove(world: World, actor: Actor, victim: Actor | None) -> None:
    _confront(world, actor, victim, "shove", "shoved", "shoved")


def _start_fight(world: World, actor: Actor, victim: Actor | None) -> None:
    _confront(world, actor, victim, "fight_started", "attacked", "attacked")


def _go_home(world: World, actor: Actor, door: dict[str, Any] | None) -> None:
    # step_world moves the visitor out once every actor has finished this tick.
    actor["visit"]["left_at"] = world["time"]


def _fall_asleep(world: World, actor: Actor, target: Any) -> None:
    record_event(world, actor, "dozed_off", f"{actor['name']} fell asleep at the table")


def _wake_up(world: World, actor: Actor, target: Any) -> None:
    record_event(world, actor, "woke_up", f"{actor['name']} woke up at the table")


def _settle(world: World, actor: Actor, seat: dict[str, Any] | None) -> None:
    # The chair a visitor sits down on becomes their own; taking someone else's own seat wrongs them.
    if seat is None:
        raise ValueError("Settling down needs a seat")
    if actor["seat_id"] != seat["id"]:
        for owner in world["actors"]:
            if owner["id"] != actor["id"] and owner["favorite_seat_id"] == seat["id"]:
                message = f"{actor['name']} took {owner['name']}'s seat ({seat['name']})"
                record_event(world, owner, "seat_taken", message)
                think(owner, "seat_taken", world["time"], f"{called(owner, actor)} took my seat ({seat['name']})",
                      message, about=actor)
    actor.update({"seat_id": seat["id"], "favorite_seat_id": seat["id"]})


ACTIVITIES: Mapping[str, Activity] = MappingProxyType({activity.verb: activity for activity in (
    Activity(verb="take_beer", fatigue_per_second=0.5, target_kinds=("tap",), duration=0.8, empty_target="Beer tap is empty",
             leaves_seat=True, served=True, effect=_pour, label="Get a beer", status="getting ale", pose="TakeBeer",
             doing="fetching ale", done="poured a mug of ale",
             family="refreshment",
             what="walk to the tap {target} and get a mug of ale to carry: the barkeep pours it, or they pour "
                  "their own when nobody tends the bar",
             guidance="Thirsty guests and newcomers naturally fetch a drink. It is pointless while they already "
                      "hold a mug, or when the tap has run dry."),
    # Never a candidate: the barkeep's own routine (`tavern.body.bartending`) pours for the guest waiting at the
    # tap, and a guest is refused it. The routine, not the timer, ends it.
    Activity(verb="pour_beer", duration=3.0, served=True, staff_only=True, label="Pour a beer", status="pouring",
             pose="PouringBeer", doing="pouring ale behind the bar", done="poured a mug of ale",
             family="refreshment",
             what="pour a mug of ale for the guest waiting at the tap",
             guidance="Nobody chooses it: the barkeep pours for whoever waits at the tap."),
    Activity(verb="drink", fatigue_per_second=0.4, duration=3.0, requires_item="beer",
             needs=MappingProxyType({"thirst": -60, "bladder": 25}), effect=_drink, label="Drink beer", interruptible=True,
             status="sipping ale", pose="Drinking", doing="drinking", done="drank a beer",
             family="refreshment",
             what="drink the mug of ale they are holding",
             guidance="Sipping ale at the table is the heart of a tavern evening; it quenches thirst but fills "
                      "the bladder."),
    Activity(verb="rest", target_kinds=("chair",), duration=3.0,
             label="Rest", pose="Seated", interruptible=True, doing="resting", done="rested",
             family="resting",
             what="rest on the chair {target}",
             guidance="A short sit-down; it does not ease tiredness, only sleep does."),
    Activity(verb="sit", target_kinds=("chair",), duration=14.0,
             on_arrival=_settle, label="Sit at a table", status="seated", pose="Seated",
             interruptible=True,
             doing="heading to a seat", done="sat a while",
             family="resting",
             what="sit in their own seat {target} for a while",
             guidance="Sitting in their own seat is a guest's natural resting state: it is "
                      "where they sip their ale, and it lets them chat with whoever shares the table. Getting "
                      "up needs a reason."),
    Activity(verb="talk", fatigue_per_second=0.1, partner=True, duration=8.0, on_arrival=_open_scene, label="Chat with a neighbor",
             status="chatting", pose="Talking",
             sound=Sound("chat", 0.25, 6.0, "a conversation"), doing="talking", done="chatted",
             family="company",
             what="start a conversation with {target}, who sits at their table or stands beside them",
             guidance="It eases the wish for company of both and lets them share where the beer, WC and darts "
                      "are. Someone they dislike is poor company: an insult to a guest who already thinks ill of them "
                      "ends in a quarrel, leaving both in a sour mood and thinking less of each other. Right after "
                      "a chat, with their wish for company satisfied, a quiet sip or a rest is more natural "
                      "than yet another chat."),
    Activity(verb="join_conversation", fatigue_per_second=0.1, partner=True, joins=True, duration=8.0, on_arrival=_join_scene,
             label="Join a conversation", status="chatting", pose="Talking", doing="joining a conversation",
             done="joined a conversation",
             family="company",
             what="join the conversation {target} is having at their table or beside them",
             guidance="Joining company already talking eases the wish for company like a chat of their own and "
                      "is how a stranger gets to know people; it is poor manners to barge in on someone who "
                      "wronged them tonight."),
    # Leaning on the bar is how a guest comes within reach of the barkeep: standing there they are side by side
    # with him (`scenes.side_by_side`), and chat with him as with a neighbour.
    Activity(verb="stand_at_bar", fatigue_per_second=0.15, target_kinds=("bar",), shared_target=True, duration=12.0, leaves_seat=True,
             needs=MappingProxyType({"boredom": -20, "social": -10}), label="Stand at the bar", status="at the bar",
             interruptible=True, doing="leaning on the bar", done="stood at the bar", family="company",
             what="walk over to the bar {target} and lean on it, where the barkeep chats with whoever stands there",
             guidance="Leaning on the bar puts a guest within reach of the barkeep, who tends it all evening, "
                      "passes on what he hears and answers a word or two; it eases boredom and the wish for "
                      "company a little. It means leaving their seat for a while."),
    Activity(verb="play_darts", fatigue_per_second=0.8, target_kinds=("darts",), duration=10.0, leaves_seat=True,
             needs=MappingProxyType({"boredom": -65}), label="Play darts", status="darts", pose="Darts", interruptible=True,
             sound=Sound("thud", 0.25, 10.0, "darts thudding into the board"),
             doing="playing darts", done="played darts",
             family="pastime",
             what="play a round of darts at {target}",
             guidance="A lively pastime for a bored guest; it means leaving their seat for a while."),
    # Never a candidate: only an accepted `dice_together` invitation (or the debug panel) sends a guest to a
    # dice chair. The game, not the timer, ends it.
    Activity(verb="play_dice", fatigue_per_second=0.15, target_kinds=("dice_chair",), duration=30.0, game=True, leaves_seat=True,
             needs=MappingProxyType({"boredom": -70, "social": -20}), label="Play dice", status="dice",
             pose="TalkingSeated", sound=Sound("dice", 0.25, 8.0, "dice rattling on a table"),
             doing="playing dice", done="played dice", family="pastime",
             what="sit at the dice table {target} for a game of dice they agreed to",
             guidance="A seat at a game they agreed to: it eases boredom and the wish for company, and lasts until "
                      "the dice are thrown."),
    # A crowd round a game under way: it ends with the game (or at once when there is none).
    Activity(verb="watch_dice", fatigue_per_second=0.1, target_kinds=("dice_table",), shared_target=True, duration=25.0, game=True,
             leaves_seat=True, needs=MappingProxyType({"boredom": -45}), label="Watch the dice",
             status="watching dice", interruptible=True, doing="watching a game of dice",
             done="watched a game of dice", family="pastime",
             what="walk over to the dice table {target} and watch the game being played there",
             guidance="A game of dice draws a crowd: watching eases boredom, and curious guests love to see who "
                      "wins. It means leaving their seat until the game ends."),
    # Offered only to a guest with a grudge, a temper and, as drink loosens it, the nerve (`tavern.social.hostility`).
    Activity(verb="shove", fatigue_per_second=3.0, near_person=True, duration=1.0, effect=_shove, label="Shove", status="shoving",
             doing="shoving someone", done="shoved someone", family="confront",
             what="shove {target}, who sits at their table or stands beside them, hard enough that the whole room "
                  "turns to look",
             guidance="A rough act and a rare one, never a first answer: only a guest with a real grudge (someone "
                      "who insulted them, quarreled with them, took their seat or cut in line, and whom they think "
                      "ill of) and a short temper, more so with drink in them, would do it. Everyone hears it, the "
                      "one shoved will not forget it, and it may lead to worse. Most guests, even angry ones, "
                      "choose something else."),
    Activity(verb="start_fight", fatigue_per_second=5.0, near_person=True, duration=2.0, effect=_start_fight, label="Start a fight",
             status="fighting", doing="starting a fight", done="started a fight", family="confront",
             what="pick a fight with {target}, who sits at their table or stands beside them",
             guidance="The rarest act of the evening: a fistfight with someone they think ill of after a recent "
                      "wrong, which only a hot temper, usually helped by plenty of drink, brings a guest to. The "
                      "whole room hears it, the one attacked will not forget it, and it can end in injury. Even "
                      "an angry guest almost always chooses something else."),
    Activity(verb="give", fatigue_per_second=0.5, near_person=True, names_item=True, duration=1.5, effect=_give, label="Give",
             status="giving", pose="Giving", doing="handing something over", done="gave something away",
             family="company", what="hand {item} to {target}, who sits at their table or stands beside them",
             guidance="A kindness between people who get on: a drink for a thirsty friend, a remedy for someone "
                      "worried about sickness, a keepsake for someone they like. It costs the giver what they hand "
                      "over, and someone who dislikes them may refuse it."),
    Activity(verb="bring_drink", fatigue_per_second=0.5, near_person=True, opens_errand=True, duration=0.5, effect=_bring_drink,
             label="Bring a drink", status="fetching a drink", doing="going to fetch someone an ale",
             done="went to fetch someone an ale", family="fetching",
             what="fetch a mug of ale and bring it to {target}, who sits at their table or stands beside them",
             guidance="A kindness for company whose hands are empty: it takes a trip to the tap and back, so it "
                      "suits someone with nothing pressing of their own, and the one they bring it for may still "
                      "refuse it."),
    Activity(verb="use_toilet", fatigue_per_second=0.5, target_kinds=("toilet",), duration=2.0, leaves_seat=True,
             needs=MappingProxyType({"bladder": -65}), label="Use the toilet", status="WC", pose="Bathroom",
             doing="heading to the WC", done="used the WC",
             family="wc",
             what="use the WC {target}",
             guidance="Necessary once the bladder presses, pointless before."),
    Activity(verb="inspect", fatigue_per_second=0.5, duration=0.8, label="Explore the room", doing="looking around", interruptible=True,
             done="looked around",
             family="exploring",
             what="explore the room to discover or re-check places",
             guidance="Worthwhile only when something they need has not been found yet; otherwise it is aimless "
                      "wandering."),
    Activity(verb="wait", duration=1.0, label="Wait a little", doing="waiting", interruptible=True, done="waited",
             family="idling",
             what="wait a moment and do nothing",
             guidance="Idling where they stand is rarely the most natural thing."),
    Activity(verb="leave", fatigue_per_second=0.5, target_kinds=("door",), shared_target=True, duration=1.0, effect=_go_home, label="Go home",
             status="going home", doing="heading for the door", done="left",
             family="going_home",
             what="leave the inn for the night through {target}, ending their visit for good",
             guidance="Going home is the natural end of an evening, not a failure. It is the right move when "
                      "they are content: they have stayed a good while (several minutes of "
                      "`self.visit.seconds`), drunk their fill (two or three beers in `self.visit.beers`) and "
                      "their needs are mostly low, or when their company has gone home and the evening has run "
                      "its course; after a long evening and several beers, a guest left alone in the inn "
                      "naturally heads home. Deep tiredness late in the evening is a reason to go home to bed, "
                      "unless they would rather sleep it off in their seat. It is also right when the evening has "
                      "gone wrong: the beer has run out (the tap shows stock 0 when last seen) while they are still thirsty, someone took "
                      "their seat, someone offended them or they had a quarrel and their mood has soured (see the "
                      "mood, opinions and what still rankles in the situation), "
                      "or their needs keep going unmet. Leaving is a poor choice when they have just arrived, "
                      "still hold an undrunk mug, want a drink that is still available, or are enjoying good "
                      "company. Impatient guests walk out sooner when their mood sours; comfort-loving guests "
                      "linger in a cosy seat."),
    # Gazing at the flames or the road outside is a gentler pastime than darts.
    Activity(verb="watch", fatigue_per_second=0.1, target_kinds=("window", "fireplace"), duration=8.0,
             needs=MappingProxyType({"boredom": -40}), label="Watch the fire or the view", interruptible=True,
             status="at the window", doing="admiring the view", done="admired the view",
             family="pastime",
             what="stand by {target} and watch it for a while",
             guidance="Gazing into the flames of the fireplace or out of a window at the road is a quiet "
                      "pleasure that eases boredom more gently than darts. Comfort-loving guests especially "
                      "enjoy the warmth of the fire, curious ones the view outside. It means leaving their seat "
                      "for a while."),
    # A wasted guest at their table nods off by themselves (`dozing.nodding_off`); a tired one may also choose it.
    # Either way a loud enough sound wakes them (`dozing.waking_sound`) and a quiet one does not.
    Activity(verb="doze", fatigue_per_second=-0.75, duration=40.0, label="Sleep at the table", status="asleep",
             pose="Seated", interruptible=True, asleep=True, seated=True, on_arrival=_fall_asleep, effect=_wake_up,
             doing="asleep at the table", done="slept at the table", family="resting",
             what="put their head down and sleep a while right here in their seat (it restores some energy; nobody "
                  "at an inn minds a sleeper, and a loud noise will wake them)",
             guidance="Tiredness is the reason, and drink makes it likelier: a tired guest who has had a few "
                      "drinks naturally dozes off at the table, and the others let them be. A sober, content "
                      "guest who is tired late in the evening usually goes home to bed instead. It is pointless "
                      "when they are not tired."),
    # A decision step, not a world action: a second evaluation picks the chair to `sit` on.
    Activity(verb="seating", duration=None,
             family="seat_choice",
             what="find a seat: choose a free chair at one of the tables and sit down",
             guidance="A separate decision picks the chair, which becomes their own seat for the rest of the "
                      "visit. Visitors who have just come in usually want to sit down and have a beer first. If "
                      "they already have a seat of their own, this means moving to another table, which is "
                      "worth it mainly to join company when they feel lonely."),
    # Not a world action of its own: the world reads it as using the place, from the front of its line.
    Activity(verb="cut_in_line", target_kinds=("tap", "toilet", "darts"), duration=None, family="cutting_in",
             label="Cut in line",
             what="push to the front of the line for {target}, ahead of everyone waiting",
             guidance="Rude: everyone pushed past resents it and remembers who did it. Only an impatient guest "
                      "with a pressing need and a long line ahead would consider it."),
)})


# Activity families, each with the words that complete "How natural is it for them, right now, to ...".
# A family groups the activities that answer the same wish, so the first decision weighs wishes
# and the second only the ways to fulfil the chosen one.
FAMILIES: Mapping[str, str] = MappingProxyType({
    "refreshment": "get something to drink",
    "resting": "sit down for a rest, or sleep a while where they sit",
    "seat_choice": "find a seat at a table, or move to another one",
    "company": "chat with someone at their table or beside them, join a conversation, lean on the bar, or hand "
               "someone something they carry",
    "pastime": "pass the time",
    "wc": "use the WC",
    "exploring": "explore the room",
    "idling": "wait a moment",
    "going_home": "go home for the night",
    "cutting_in": "push to the front of a line instead of waiting",
    "fetching": "fetch someone at their table or beside them a drink from the tap",
    "confront": "shove someone who wronged them, or start a fight",
})


def client_activities(activities: Mapping[str, Activity]) -> dict[str, dict[str, Any]]:
    """Describe the verbs the world runs, for the browser client.

    Args:
        activities: Activity table.
    Returns:
        Per world verb: command label, status text, pose, target kinds, and whether it
        targets another visitor (`partner`), plus `names_item` for a verb that also names an item. Decision
        steps such as `seating` are left out.
    """
    return {verb: {"label": activity.label, "status": activity.status, "pose": activity.pose,
                   "target_kinds": list(activity.target_kinds), "partner": activity.partner or activity.near_person,
                   **({"names_item": True} if activity.names_item else {})}
            for verb, activity in activities.items() if activity.duration is not None}
