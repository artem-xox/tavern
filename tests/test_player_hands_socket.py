"""The player's hands over the socket: walk to a spot, ask what is open at the tap, take a beer and drink it."""

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from tavern.hall.world import step_world
from tavern.server.api import create_app
from test_app import room

SESSION = "device-hands"


def reply_to(socket: Any, command: dict[str, Any], kind: str = "snapshot") -> dict[str, Any]:
    """Send a command and read messages until one of the given type arrives (periodic snapshots are skipped)."""
    socket.send_json(command)
    while True:
        message = socket.receive_json()
        if message["type"] == kind:
            return dict(message)


def run(world: dict[str, Any], seconds: float) -> None:
    """Advance the world by hand, as the runtime's ticker would."""
    for _ in range(round(seconds * 10)):
        step_world(world, 0.1)


def test_the_player_walks_to_a_cell_then_takes_a_beer_and_drinks_it_through_act(tmp_path: Path) -> None:
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(room()))
    application = create_app(map_path, tmp_path / "save.json", {"typesafe_api_key": None}, run_loop=False)
    with TestClient(application) as connection, connection.websocket_connect(f"/ws?session={SESSION}") as socket:
        assert socket.receive_json()["type"] == "snapshot"
        world = application.state.sessions.runtimes[SESSION].world
        world.update(paused=False, player={"actor_id": "ada", "steering": True})
        ada = world["actors"][0]
        ada["needs"]["thirst"] = 90.0

        walk = {"id": "walk_to:2,3", "verb": "walk_to", "target_id": None, "cell": [2, 3]}
        reply_to(socket, {"type": "act", "action": walk})
        run(world, 5)
        assert ([ada["x"], ada["y"]], ada["status"], ada["decision"]["source"]) == ([2, 3], "idle", "player")

        listed = reply_to(socket, {"type": "options", "target_id": "tap"}, "options")
        assert socket.receive_json()["type"] == "snapshot"
        assert [item["action"]["verb"] for item in listed["options"]] == ["take_beer"]
        reply_to(socket, {"type": "act", "action": listed["options"][0]["action"]})
        run(world, 10)
        assert (ada["inventory"]["beer"], ada["action"]) == (1, None)

        reply_to(socket, {"type": "act", "action": {"id": "drink", "verb": "drink", "target_id": None}})
        run(world, 10)
        assert (ada["inventory"]["beer"], ada["action"]) == (0, None)


def test_a_refused_act_is_answered_with_an_error_and_the_socket_stays_open(tmp_path: Path) -> None:
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(room()))
    application = create_app(map_path, tmp_path / "save.json", {"typesafe_api_key": None}, run_loop=False)
    with TestClient(application) as connection, connection.websocket_connect(f"/ws?session={SESSION}") as socket:
        assert socket.receive_json()["type"] == "snapshot"
        refusal = reply_to(socket, {"type": "act", "action": {"id": "x", "verb": "wait", "target_id": None}}, "error")
        assert "needs a player" in refusal["message"]
        assert reply_to(socket, {"type": "pause", "paused": True})["state"]["paused"] is True
