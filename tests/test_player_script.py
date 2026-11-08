"""The player script: timed player commands for a headless evening."""

import json
from pathlib import Path
from typing import Any

import pytest

from tavern.evening.player_script import PlayerScript, Step, parse_player_script

SAY = {"type": "say", "text": "Hello.", "to": "auto"}


def script(*steps: Any, player: Any = "monroe") -> dict[str, Any]:
    return {"player": player, "steps": list(steps)}


def step(at: Any, command: Any = SAY) -> dict[str, Any]:
    return {"at": at, "command": command}


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param(script(), PlayerScript("monroe", ()), id="empty-steps"),
        pytest.param(script(step(20.0)), PlayerScript("monroe", (Step(20.0, SAY),)), id="one-say"),
        pytest.param(script(step(5), step(5.0)), PlayerScript("monroe", (Step(5.0, SAY), Step(5.0, SAY))),
                     id="same-at-twice"),
        pytest.param(script(step(1, {"type": "steer", "on": True}), step(2, {"type": "typing"})),
                     PlayerScript("monroe", (Step(1.0, {"type": "steer", "on": True}),
                                             Step(2.0, {"type": "typing"}))), id="steer-and-typing"),
    ],
)
def test_parse_good_script(data: dict[str, Any], expected: PlayerScript) -> None:
    assert parse_player_script(data) == expected


@pytest.mark.parametrize(
    ("data", "named"),
    [
        pytest.param(script(step(1, {"type": "dance"})), "dance", id="unknown-type"),
        pytest.param(script(step(1, {"type": "options"})), "options", id="options-step"),
        pytest.param(script(step(9), step(3)), "3", id="at-goes-back"),
        pytest.param(script(step("soon")), "soon", id="at-not-a-number"),
        pytest.param(script(step(True)), "True", id="at-is-a-bool"),
        pytest.param(script({"at": 1}), "command", id="missing-command"),
        pytest.param(script({"at": 1, "command": SAY, "why": "x"}), "why", id="extra-field"),
        pytest.param({"steps": []}, "player", id="missing-player"),
        pytest.param(script(player=""), "player", id="empty-player"),
        pytest.param(["monroe"], "mapping", id="not-a-mapping"),
    ],
)
def test_parse_bad_script_names_the_value(data: Any, named: str) -> None:
    with pytest.raises(ValueError, match=named):
        parse_player_script(data)


@pytest.mark.parametrize("name", [pytest.param("monroe_meddles", id="monroe-meddles"),
                                  pytest.param("locals_smoke", id="locals-smoke")])
def test_the_sample_scripts_parse(name: str) -> None:
    path = Path(__file__).resolve().parents[1] / "data" / "players" / f"{name}.json"
    assert parse_player_script(json.loads(path.read_text())).steps
