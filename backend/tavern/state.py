"""The shape of the authoritative world: its records and rules, and finding a visitor in it.

The world is a plain JSON-ready dict (it is also the save and the snapshot), so these
`TypedDict`s describe it for the checker and for readers; nothing builds or validates from them.
Records that have a module of their own (`Conversation`, `Thought`, `Gaze`, ...) are named from
there; they are imported for the checker only, because those modules import this one.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Literal, NotRequired, TypedDict

if TYPE_CHECKING:
    from tavern.cards import Card
    from tavern.expression import Emote, Gaze
    from tavern.hearing import Stimulus
    from tavern.intentions import Intention
    from tavern.invitations import Errand
    from tavern.scenario import ExpectedGuest
    from tavern.scenes import Conversation
    from tavern.thoughts import Relation, Thought
    from tavern.ties import OwnTie

# What a visitor's body is doing: nothing, walking a route, using a place, held up on a route,
# or standing in a line.
Status = Literal["idle", "walking", "interacting", "waiting", "queued"]


class Visit(TypedDict):
    """One evening's tally for a visitor; `left_at` is set when they head home."""

    seconds: float
    beers: int
    grievances: list[str]
    left_at: NotRequired[float]


class Knowledge(TypedDict):
    """What a visitor has seen: the places they remember (`objects`, by ID) and the cells they know."""

    objects: dict[str, dict[str, Any]]
    cells: list[list[int]]


class Decision(TypedDict):
    """The last decision, for the inspector: who made it, the scores, and why it fell back."""

    source: str
    scores: dict[str, float]
    error: str | None
    seat: NotRequired[dict[str, Any]]
    family: NotRequired[dict[str, Any]]


class Actor(TypedDict):
    """A visitor in the hall. Fields starting with an underscore are the action's progress and
    are saved with it."""

    id: str
    name: str
    color: str
    sprite: str
    x: int
    y: int
    traits: dict[str, float]
    card: "Card | None"
    ties: "list[OwnTie]"
    needs: dict[str, float]
    inventory: dict[str, int]
    status: Status
    action: dict[str, Any] | None
    path: list[list[int]]
    seat_id: str | None
    favorite_seat_id: str | None
    visit: Visit
    thoughts: "list[Thought]"
    relations: "dict[str, Relation]"
    drunkenness: float
    knowledge: Knowledge
    memory: list[dict[str, Any]]
    decision: Decision
    facing: str | None
    gaze: "Gaze | None"
    emote: "Emote | None"
    interrupted_at: float | None
    intention: "Intention | None"
    _move_elapsed: float
    _remaining: float
    _blocked_for: float
    _spot: list[int] | None


class QueueRules(TypedDict):
    """Seconds a visitor waits in line: a base, plus per unit of patience and of urgency."""

    base: float
    patience: float
    urgency: float


class AttentionRules(TypedDict):
    """Salience of a glance and of an interrupt, the damping per wall, and how long a gaze lasts."""

    glance: float
    interrupt: float
    wall_damping: float
    glance_seconds: float
    turn_seconds: float


class DrunkennessRules(TypedDict):
    """A middling drinker's rise per beer, the fall per second, and the doze chance per second."""

    per_beer: float
    per_second: float
    doze_per_second: float


class ConversationRules(TypedDict):
    """Timing, size and reach of scenes (see `tavern.scenes` and `tavern.turns`)."""

    opening: float
    min_gap: float
    chars_per_second: float
    turn_timeout: float
    relief: float
    satisfied: float
    max_participants: int
    reach: int
    pressing: float


class Rules(TypedDict):
    """The tunable rules of the world, kept in every save."""

    move_seconds: float
    blocked_timeout: float
    vision_radius: int
    need_rates: dict[str, float]
    durations: dict[str, float]
    quarrel_per_beer: float
    quarrel_max: float
    queue_patience: QueueRules
    queue_needs: dict[str, str]
    attention: AttentionRules
    emote_seconds: dict[str, float]
    long_wait: float
    drunkenness: DrunkennessRules
    conversation: ConversationRules


class HallMap(TypedDict):
    """The hall: its size in cells, blocked cells, and objects (tables, chairs, the tap, ...)."""

    width: int
    height: int
    tile_size: int
    blocked: list[list[int]]
    objects: list[dict[str, Any]]


class World(TypedDict):
    """The whole evening: clock, hall, people, log, sounds, scenes and errands."""

    schema_version: int
    seed: int
    tick: int
    time: float
    paused: bool
    speed: float
    map: HallMap
    actors: list[Actor]
    departed: list[Actor]
    expected: "list[ExpectedGuest]"
    closes_at: float | None
    events: list[dict[str, Any]]
    stimuli: "list[Stimulus]"
    next_stimulus_id: int
    conversations: "list[Conversation]"
    next_conversation_id: int
    invitations: "list[Errand]"
    rules: Rules


def find_actor(world: Mapping[str, Any], actor_id: Any) -> Actor | None:
    """Find a visitor in the hall.

    Args:
        world: World whose `actors` are searched; visitors who left are not.
        actor_id: ID to look for; anything that matches no visitor finds none.

    Returns:
        The visitor's record, or None.
    """
    return next((item for item in world["actors"] if item["id"] == actor_id), None)
