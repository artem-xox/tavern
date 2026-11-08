"""A scripted player: timed player commands for a headless evening."""

from collections.abc import Mapping
from dataclasses import dataclass
import math
from typing import Any

# The commands a client sends as the player; `options` only asks a question, so a script never has it.
SCRIPTED_TYPES = ("steer", "act", "say", "typing")


# How the log opens the `control` event of a refused step ("Player script: say refused: ..."); metrics count them.
REFUSAL_PREFIX = "Player script: "


@dataclass(frozen=True)
class Step:
    """One command due at game second `at`."""

    at: float
    command: Mapping[str, Any]


@dataclass(frozen=True)
class PlayerScript:
    """The guest a script plays (`player`) and its steps in time order."""

    player: str
    steps: tuple[Step, ...]


def parse_player_script(data: Any) -> PlayerScript:
    """Check a script read from JSON and shape it.

    Args:
        data: `{"player": str, "steps": [{"at": number, "command": {...}}]}`. Steps with the same `at` run in order.

    Returns:
        The script.

    Raises:
        ValueError: Naming the bad value: not a mapping, a missing or extra field, an empty player, an `at` that
            is not a number or is earlier than the step before, or a command of an unknown type (`options` too).
    """
    fields = _mapping(data, "script", {"player", "steps"})
    player = fields["player"]
    if not isinstance(player, str) or not player:
        raise ValueError(f"Script player must be a nonempty guest id, not {player!r}")
    raw = fields["steps"]
    if not isinstance(raw, list):
        raise ValueError(f"Script steps must be a list, not {raw!r}")
    steps: list[Step] = []
    for item in raw:
        parsed = _step(item)
        if steps and parsed.at < steps[-1].at:
            raise ValueError(f"Script step at {parsed.at!r} comes after a step at {steps[-1].at!r}")
        steps.append(parsed)
    return PlayerScript(player, tuple(steps))


def _step(item: Any) -> Step:
    fields = _mapping(item, "step", {"at", "command"})
    at = fields["at"]
    # A bool is an int in Python, and a nan never compares, so neither is a time.
    if isinstance(at, bool) or not isinstance(at, (int, float)) or not 0 <= at < math.inf:
        raise ValueError(f"Step at must be a nonnegative number of game seconds, not {at!r}")
    command = fields["command"]
    if not isinstance(command, Mapping) or command.get("type") not in SCRIPTED_TYPES:
        kind = command.get("type") if isinstance(command, Mapping) else command
        raise ValueError(f"Step command type must be one of {SCRIPTED_TYPES}, not {kind!r}")
    return Step(float(at), command)


def _mapping(data: Any, what: str, names: set[str]) -> Mapping[str, Any]:
    if not isinstance(data, Mapping):
        raise ValueError(f"A {what} must be a mapping, not {data!r}")
    missing = sorted(names - set(data))
    if missing:
        raise ValueError(f"A {what} is missing {', '.join(missing)}")
    extra = sorted(set(data) - names)
    if extra:
        raise ValueError(f"A {what} has unknown fields {', '.join(extra)}")
    return data
