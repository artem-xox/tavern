"""The lineup: the guests picked on the start screen, their evening's length, and the API that offers them."""

from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from tavern.adapters.characters import load_catalog
from tavern.evening.lineup import casts_public, lineup_scenario
from tavern.evening.scenario import open_evening
from tavern.server.api import create_app
from tavern.server.runtime import TavernRuntime

ROOT = Path(__file__).resolve().parents[1]
CATALOG = load_catalog(ROOT / "characters")
TEMPLATES = {name: json.loads((ROOT / "data" / "scenarios" / f"{name}.json").read_text())
             for name in ("locals", "guests")}


def lineup(cast: str, ids: list[str], minutes: float = 5) -> Any:
    return lineup_scenario(TEMPLATES, CATALOG, cast, ids, minutes)


@pytest.mark.parametrize("cast, ids", [
    pytest.param("locals", ["edda"], id="one-local"),
    pytest.param("locals", ["saye", "rurik"], id="two-locals-keep-picked-order"),
    pytest.param("locals", ["edda", "rurik", "toren", "brida", "calder", "saye"], id="all-six-locals"),
    pytest.param("guests", ["greta", "trump"], id="both-guests"),
])
def test_a_lineup_seats_exactly_the_picked_people_with_hob_behind_the_bar(cast: str, ids: list[str]) -> None:
    scenario = lineup(cast, ids)
    assert ([guest["id"] for guest in scenario.guests], [member["id"] for member in scenario.staff]) == (ids, ["hob"])


@pytest.mark.parametrize("minutes, closes_at, last_call_at", [
    pytest.param(5, 300, 270, id="the-web-default"),
    pytest.param(1, 60, 54, id="shortest"),
    pytest.param(10.5, 630, 567, id="fractional"),
])
def test_the_evening_lasts_the_chosen_minutes_with_last_call_at_nine_tenths(
        minutes: float, closes_at: float, last_call_at: float) -> None:
    scenario = lineup("locals", ["edda", "rurik"], minutes)
    assert (scenario.closes_at, scenario.last_call_at) == (closes_at, last_call_at)


def arrivals(scenario: Any) -> list[float]:
    world = open_evening(json.loads((ROOT / "data" / "tavern.json").read_text()), scenario, 1)
    return sorted(item["arrives_at"] for item in world["expected"])


@pytest.mark.parametrize("cast, ids, minutes, gap", [
    pytest.param("locals", ["edda", "rurik", "toren", "brida", "calder", "saye"], 5, 15, id="six-locals-fifteen-seconds-apart"),
    pytest.param("guests", ["trump", "greta"], 5, 15, id="two-guests-fifteen-seconds-apart"),
    pytest.param("locals", ["edda", "rurik", "toren", "brida", "calder", "saye"], 1, 6, id="a-short-evening-squeezes-them-into-half"),
])
def test_guests_come_in_one_by_one_not_as_a_crowd(cast: str, ids: list[str], minutes: float, gap: float) -> None:
    times = arrivals(lineup(cast, ids, minutes))
    assert ([round(b - a, 6) for a, b in zip(times, times[1:])], times[-1] < minutes * 60) == (
        [gap] * (len(ids) - 1), True)


@pytest.mark.parametrize("ids, told", [
    pytest.param(["edda"], {"margrave_fever"}, id="only-the-news-a-picked-guest-knows"),
    pytest.param(["saye", "rurik"], {"cloth_robbery", "deserters", "salt_toll"} , id="shared-news-keeps-the-picked-knowers"),
])
def test_news_is_told_only_by_guests_who_are_there(ids: list[str], told: set[str]) -> None:
    scenario = lineup("locals", ids)
    known = {guest for item in scenario.news for guest in item.get("known_by", [])}
    assert (known <= set(ids), {item["id"] for item in scenario.news} <= told) == (True, True)


def test_a_lone_healer_comes_in_well_because_nobody_else_could_fall_ill() -> None:
    assert lineup("locals", ["edda"]).ailing_fatigue is None


@pytest.mark.parametrize("ids, minutes, message", [
    pytest.param([], 5, "1 to 6", id="nobody"),
    pytest.param(["edda"] * 2, 5, "twice", id="duplicate"),
    pytest.param(["edda", "rurik", "toren", "brida", "calder", "saye", "edda"], 5, "1 to 6", id="seven"),
    pytest.param(["trump"], 5, "not in the locals", id="from-another-cast"),
    pytest.param(["hob"], 5, "not in the locals", id="the-barkeep"),
    pytest.param(["nobody"], 5, "Unknown character", id="unknown-character"),
    pytest.param(["edda"], 0, "Evening length", id="zero-minutes"),
    pytest.param(["edda"], True, "Evening length", id="boolean-minutes"),
    pytest.param("edda", 5, "list", id="a-string-instead-of-a-list"),
])
def test_a_malformed_lineup_is_refused_by_name(ids: Any, minutes: Any, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        lineup("locals", ids, minutes)


def test_an_unknown_cast_is_refused() -> None:
    with pytest.raises(ValueError, match="Unknown cast 'staff'"):
        lineup("staff", ["hob"])


def test_the_cast_listing_shows_each_face_with_its_occupation() -> None:
    casts = {item["id"]: item for item in casts_public(CATALOG, TEMPLATES)}
    greta = next(item for item in casts["guests"]["characters"] if item["id"] == "greta")
    assert (casts["guests"]["title"], [item["id"] for item in casts["guests"]["characters"]], greta["name"],
            greta["description"], len(casts["locals"]["characters"])) == (
        "Guests", ["greta", "monroe", "musk", "putin", "queen", "thatcher", "trump", "tyson", "zelensky"], "Greta", "young climate campaigner, a parody of Greta Thunberg", 6)


def runtime(tmp_path: Path) -> TavernRuntime:
    room = json.loads((ROOT / "data" / "tavern.json").read_text())
    return TavernRuntime(room, tmp_path / "save.json", {"typesafe_api_key": None},
                         lineup=lambda cast, ids, minutes: lineup(cast, ids, minutes))


def test_the_start_command_opens_a_running_evening_for_the_picked_guests(tmp_path: Path) -> None:
    opened = runtime(tmp_path)
    opened.command({"type": "start", "cast": "guests", "guests": ["greta"], "minutes": 5})
    world = opened.world
    assert ([item["id"] for item in [*world["actors"], *world["expected"]] if item["id"] != "hob"],
            world["closes_at"], world["paused"], world["speed"]) == (["greta"], 300, False, 1.0)


def test_restart_replays_the_picked_lineup(tmp_path: Path) -> None:
    opened = runtime(tmp_path)
    opened.command({"type": "start", "cast": "locals", "guests": ["saye"], "minutes": 2})
    opened.command({"type": "reset"})
    assert [item["id"] for item in [*opened.world["actors"], *opened.world["expected"]]
            if item["id"] != "hob"] == ["saye"]


@pytest.mark.parametrize("command, message", [
    pytest.param({"type": "start", "cast": "guests", "guests": [], "minutes": 5}, "1 to 6", id="nobody"),
    pytest.param({"type": "start", "cast": "guests", "minutes": 5}, "guests", id="no-guests-field"),
    pytest.param({"type": "start", "guests": ["greta"], "minutes": 5}, "cast", id="no-cast-field"),
    pytest.param({"type": "start", "cast": "guests", "guests": ["greta"]}, "Evening length", id="no-minutes"),
])
def test_a_malformed_start_changes_nothing(tmp_path: Path, command: dict[str, Any], message: str) -> None:
    opened = runtime(tmp_path)
    before = opened.world
    with pytest.raises(ValueError, match=message):
        opened.command(command)
    assert opened.world is before


def test_a_runtime_without_lineups_refuses_to_start_one() -> None:
    room = json.loads((ROOT / "data" / "tavern.json").read_text())
    with pytest.raises(ValueError, match="No lineups"):
        TavernRuntime(room, Path("unused.json"), {"typesafe_api_key": None}).command(
            {"type": "start", "cast": "guests", "guests": ["greta"], "minutes": 5})


def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(ROOT / "data" / "tavern.json", tmp_path, {"typesafe_api_key": None}, run_loop=False,
                                 catalog_dir=ROOT / "characters", scenarios_dir=ROOT / "data" / "scenarios"))


def message_where(socket: Any, wanted: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
    """Read socket messages until one is wanted: the server also pushes a snapshot every 0.1 s, which can arrive between a command and its answer."""
    for _ in range(100):
        message = socket.receive_json()
        if wanted(message):
            return message
    raise AssertionError("The socket never sent the message that was wanted")


def test_the_api_lists_both_casts_and_starts_either(tmp_path: Path) -> None:
    with client(tmp_path) as connection, connection.websocket_connect("/ws?session=device-lineup") as socket:
        casts = connection.get("/api/casts").json()
        socket.receive_json()
        socket.send_json({"type": "start", "cast": "guests", "guests": ["trump", "greta"], "minutes": 3})
        started = message_where(socket, lambda message: message.get("state", {}).get("closes_at") == 180)["state"]
        socket.send_json({"type": "start", "cast": "locals", "guests": ["edda"], "minutes": 5})
        locals_evening = message_where(socket, lambda message: message.get("state", {}).get("closes_at") == 300)["state"]
        socket.send_json({"type": "start", "cast": "robots", "guests": ["edda"], "minutes": 5})
        refused = message_where(socket, lambda message: message.get("type") == "error")
    assert ([item["id"] for item in casts], started["closes_at"], locals_evening["closes_at"], refused["type"]) == (
        ["guests", "locals"], 180, 300, "error")


def test_the_api_has_no_casts_without_scenarios(tmp_path: Path) -> None:
    app = create_app(ROOT / "data" / "tavern.json", tmp_path, {"typesafe_api_key": None}, run_loop=False,
                     catalog_dir=ROOT / "characters")
    with TestClient(app) as connection:
        assert connection.get("/api/casts").status_code == 404


@pytest.mark.parametrize("cast, ids, pairs", [
    pytest.param("guests", ["greta", "trump"], [{"greta", "trump"}], id="famous-guests-know-each-other"),
    pytest.param("guests", ["trump"], [], id="a-lone-guest-has-nobody-to-know"),
    pytest.param("locals", ["edda", "rurik"], [], id="locals-start-as-strangers"),
])
def test_famous_guests_start_out_knowing_each_other_by_name(cast: str, ids: list[str], pairs: list[set[str]]) -> None:
    assert [{tie["a"], tie["b"]} for tie in lineup(cast, ids).ties] == pairs


@pytest.mark.parametrize("ids, kinds", [
    pytest.param(["trump", "greta"], ["bad blood"], id="a-catalog-feud-replaces-knowing-by-name"),
    pytest.param(["greta", "tyson"], ["well known"], id="an-untied-pair-know-each-other-by-name"),
    pytest.param(["trump", "greta", "tyson"], ["bad blood", "well known", "well known"], id="mixed-trio"),
])
def test_a_catalog_tie_is_not_doubled_by_knowing_by_name(ids: list[str], kinds: list[str]) -> None:
    assert sorted(tie["kind"] for tie in lineup("guests", ids).ties) == sorted(kinds)
