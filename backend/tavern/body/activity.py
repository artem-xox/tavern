"""What a verb is: the `Activity` record and the signature of its effect."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from tavern.body.hearing import Sound
from tavern.hall.state import Actor, World

# An effect receives the world, the visitor, and the target: an object, a partner, or None.
# The target is a place or, for a part in a conversation, the partner.
Effect = Callable[[World, Actor, Any], None]

# Boredom, on the 0–100 scale of needs, that a fully fun activity (`Activity.fun` of 1) takes away.
FUN_RELIEF = 100.0


@dataclass(frozen=True)
class Activity:
    """One verb: what it needs, how long it takes, what it changes, and how it is described.

    Attributes:
        verb: Action verb used in actions, events, and saved worlds.
        target_kinds: Object kinds it can target; empty for verbs without an object target.
        partner: Whether it targets another visitor instead of an object. Such a verb is a part in a
            conversation scene (`tavern.social.scenes`): the scene, not a timer, ends it.
        joins: Whether it joins the partner's scene instead of starting one with them.
        approaches: Whether the part walks first, to a spot at the table the partner is at or, when they stand in the
            open, to a free cell beside them, and then joins the partner's scene or starts one with them
            (`tavern.social.scenes`); a partner standing in the open waits for the walker (`tavern.social.walk_ups`).
        near_person: Whether it targets another visitor at the actor's table or beside them, as a chat does:
            no scene, no walking, and the timer ends it. Shoving (`tavern.social.hostility`) is such a verb, and
            fighting is one that the world ends (`held`).
        closes_in: Whether it targets another visitor and walks to a spot at the table they sit at unless the actor is
            already within reach of them, and acts there (`tavern.hall.routes`): stepping between fighters, helping
            someone up, asking a healer for a remedy. No scene.
        asks_cure: Whether the visitor it targets must be someone known to carry a cure.
        held: Whether the world, not this timer, ends it: a fight until it is decided (`tavern.body.fights`), lying where
            one fell until the condition is up (`tavern.body.wounds`); `duration` is only nominal.
        names_item: Whether the action names an item from the actor's hands in `Action.item`, as giving does.
        opens_errand: Whether it sends the actor off on an errand for the visitor it targets (see
            `tavern.social.errands`); like giving, it needs that visitor near.
        opens_project: The kind of `tavern.body.projects.PROJECTS` it opens instead of an action of its own, or None;
            the world starts the project when the verb is chosen, and the project's steps do the walking.
        chooses_chair: Whether a second decision picks the chair it is about, as for `seating`.
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
        fun: How much of boredom it relieves, 0–1: `fun × FUN_RELIEF` is taken off boredom on completion, so a game together
            relieves it most, and sitting or drinking alone not at all. It is the only source of relief from boredom: an
            activity with `fun` may not list a `boredom` change in `needs`.
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
        absorbed: Whether the visitor's eyes stay on the task: no sound turns their head (it still breaks off or
            alerts them as `interruptible` says).
        asleep: Whether the visitor sleeps while doing it: others see a sleeper, and only a loud sound wakes them.
        seated: Whether it can only be done from a seat at a table.
        stopped_at_last_call: Refusal given to anyone who starts it after the barkeep has called closing time, or None
            when it goes on. What began before the call still finishes.
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
    approaches: bool = False
    near_person: bool = False
    closes_in: bool = False
    asks_cure: bool = False
    held: bool = False
    names_item: bool = False
    opens_errand: bool = False
    opens_project: str | None = None
    chooses_chair: bool = False
    requires_item: str | None = None
    empty_target: str | None = None
    shared_target: bool = False
    leaves_seat: bool = False
    game: bool = False
    served: bool = False
    staff_only: bool = False
    fun: float = 0.0
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
    absorbed: bool = False
    asleep: bool = False
    seated: bool = False
    stopped_at_last_call: str | None = None
    sound: Sound | None = None

    def __post_init__(self) -> None:
        if isinstance(self.fun, bool) or not 0.0 <= self.fun <= 1.0:
            raise ValueError(f"Fun of {self.verb!r} must be from 0 to 1, not {self.fun!r}")
        if self.fun > 0.0:
            if "boredom" in self.needs:
                raise ValueError(f"{self.verb!r} sets boredom by `fun` and by `needs`; use one")
            object.__setattr__(self, "needs", MappingProxyType({**self.needs, "boredom": -FUN_RELIEF * self.fun}))
