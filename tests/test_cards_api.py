"""POST /api/cards/compile proposes a player's card params for confirmation, with the server's own key."""

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from tavern.app import create_default_app
from tavern.server.api import create_app
from tavern.mind.cards import PARAMS
from tavern.adapters.claude import ClaudeError
from tavern.mind.questions import Question


def text(**fields: Any) -> dict[str, Any]:
    """A player's card in words."""
    return {"name": "Bren", "occupation": "charcoal burner", "background": "Fought in two wars.",
            "temperament": "Quarrelsome when drinking.", "speech": "Loud.", "quirks": "Shows his scars.",
            "secret": "Deserted.", "goal": "Win at darts.", **fields}


class FakeClaude:
    """Answers every card question with the same object, or fails with the same error."""

    def __init__(self, answer: Any) -> None:
        self.answer, self.asked = answer, 0

    async def __call__(self, question: Question) -> Any:
        self.asked += 1
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def server(tmp_path: Path, claude: FakeClaude | None) -> TestClient:
    """Serve a bare room, with the given model port or none (offline)."""
    (tmp_path / "map.json").write_text(json.dumps({"width": 4, "height": 4, "objects": [], "actors": []}))
    return TestClient(create_app(tmp_path / "map.json", tmp_path / "saves", {}, run_loop=False, ask=claude))


def compile_card(tmp_path: Path, claude: FakeClaude | None, body: Any) -> Any:
    """Post a card to the compiler."""
    with server(tmp_path, claude) as connection:
        return connection.post("/api/cards/compile", json=body)


def test_compiled_params_come_back_for_confirmation(tmp_path: Path) -> None:
    answer = {**dict.fromkeys(PARAMS, 0.5), "brawling": 0.9}
    response = compile_card(tmp_path, FakeClaude(answer), text())
    assert (response.status_code, response.json()["params"]["brawling"], response.json()["compiled"],
            response.json()["source"]) == (200, 0.9, True, "claude")


def test_offline_server_labels_its_defaults(tmp_path: Path) -> None:
    response = compile_card(tmp_path, None, text())
    assert (response.status_code, response.json()["compiled"], response.json()["source"],
            response.json()["note"].startswith("Not compiled")) == (200, False, "offline", True)


@pytest.mark.parametrize("answer, status", [
    pytest.param({**dict.fromkeys(PARAMS, 0.5), "temper": 3}, 502, id="out-of-range-answer"),
    pytest.param({"temper": 0.5}, 502, id="malformed-answer"),
    pytest.param(ClaudeError("Claude HTTP 529"), 502, id="model-unavailable"),
])
def test_rejected_or_failed_compilations_are_reported(tmp_path: Path, answer: Any, status: int) -> None:
    response = compile_card(tmp_path, FakeClaude(answer), text())
    assert (response.status_code, "params" in response.json()) == (status, False)


@pytest.mark.parametrize("body", [
    pytest.param({}, id="empty-card"),
    pytest.param("Bren", id="malformed-card"),
    pytest.param(text(goal=""), id="blank-goal"),
    pytest.param(text(anthropic_api_key="client-key"), id="client-cannot-send-a-key"),
    pytest.param(text(params=dict.fromkeys(PARAMS, 0.5)), id="client-cannot-send-params"),
])
def test_invalid_cards_are_refused_before_asking(tmp_path: Path, body: Any) -> None:
    claude = FakeClaude(dict.fromkeys(PARAMS, 0.5))
    response = compile_card(tmp_path, claude, body)
    assert (response.status_code, claude.asked) == (422, 0)


def test_default_app_without_a_key_compiles_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with TestClient(create_default_app()) as connection:
        response = connection.post("/api/cards/compile", json=text())
    assert (response.status_code, response.json()["source"]) == (200, "offline")
