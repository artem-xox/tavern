"""Browser-facing catalog and snapshots never disclose a character secret."""

from pathlib import Path

from fastapi.testclient import TestClient

from tavern.server.api import create_app


def test_catalog_and_snapshot_hide_secrets_but_the_world_keeps_them(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    app = create_app(root / "data" / "tavern.json", tmp_path / "saves", {}, run_loop=False,
                     scenario_path=root / "data" / "scenarios" / "first_evening.json", catalog_dir=root / "characters")
    runtime = app.state.sessions.open("public-character-test")
    with TestClient(app) as connection:
        catalog = connection.get("/api/characters")
        snapshot = connection.get("/api/state", params={"session": "public-character-test"})
    assert (catalog.status_code, snapshot.status_code, "secret" in str(runtime.world)) == (200, 200, True)
    assert "secret" not in catalog.text
    people = [*snapshot.json()["state"]["actors"], *snapshot.json()["state"]["expected"],
              *snapshot.json()["state"]["departed"]]
    assert all("secret" not in person.get("card", {}) for person in people)
