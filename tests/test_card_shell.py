"""The server and the evening runner cast scenario guests from the character cards on disk."""

import json
from pathlib import Path
from typing import Any

import pytest

from tavern.app import create_default_app
from tavern.server.api import create_app


def test_default_app_casts_the_first_evening_from_presets() -> None:
    world = create_default_app().state.sessions.open("device-cards-test").world
    present = [item for item in world["actors"] if item["post"] is None]
    guests = [*present, *world["expected"]]
    assert [item["card"]["id"] for item in guests] == ["edda", "rurik", "toren", "brida", "calder", "saye"]
    assert [item["name"] for item in present[1]["ties"]] == ["Toren"]
    # The barkeep is cast from the staff cards, which the guests' presets do not include.
    assert [item["card"]["id"] for item in world["actors"] if item["post"] is not None] == ["hob"]


def files(tmp_path: Path, card: dict[str, Any]) -> dict[str, Path]:
    """Write a hall, a one-guest scenario cast from `ada`, and a character folder holding `card`."""
    hall = {"width": 9, "height": 6, "blocked": [[x, 5] for x in range(9) if x != 4], "objects": [
        {"id": "door", "kind": "door", "name": "Door", "x": 4, "y": 5, "interaction_spots": [[4, 4]]}]}
    scenario = {"guests": [{"id": "ada", "name": "Ada", "color": "#a08060", "sprite": "visitor", "card": "ada",
                            "arrives_at": 0}], "arrival": {"needs": {}}, "closes_at": 300}
    (tmp_path / "characters").mkdir()
    (tmp_path / "characters" / "ada.json").write_text(json.dumps(card))
    (tmp_path / "map.json").write_text(json.dumps(hall))
    (tmp_path / "scenario.json").write_text(json.dumps(scenario))
    return {"map_path": tmp_path / "map.json", "scenario_path": tmp_path / "scenario.json",
            "characters_dir": tmp_path / "characters"}


def ada(**fields: Any) -> dict[str, Any]:
    """Ada's card, with middling params."""
    params = dict.fromkeys(("patience", "temper", "sociability", "courage", "strength", "brawling", "tolerance",
                            "comfort", "curiosity"), 0.5)
    return {"id": "ada", "name": "Ada", "sprite": "visitor", "occupation": "ferrywoman", "background": "The ford.",
            "temperament": "Calm.", "speech": "Short.", "quirks": "Counts coins.", "secret": "Smugglers.",
            "goal": "News of the toll.", "params": params, **fields}


def test_server_reads_the_cards_it_is_given(tmp_path: Path) -> None:
    app = create_app(save_dir=tmp_path / "saves", ai_config={}, run_loop=False, **files(tmp_path, ada()))
    assert app.state.sessions.open("device-cards-test").world["actors"][0]["card"]["goal"] == "News of the toll."


def test_server_refuses_an_invalid_card(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        create_app(save_dir=tmp_path / "saves", ai_config={}, run_loop=False, **files(tmp_path, ada(goal="")))
