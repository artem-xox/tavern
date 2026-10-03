"""Whether Jev and Claude can be used: classified failures, a window of recent calls, probes and banners."""

import asyncio
from typing import Any

import pytest

from tavern.adapters.claude import ClaudeError
from tavern.adapters.jev import JevError
from tavern.mind.model_health import HealthBoard, banner, blocking, classify, judge


@pytest.mark.parametrize("error, status", [
    pytest.param(JevError("Jev HTTP 401", 401), "auth", id="jev-unauthorized"),
    pytest.param(ClaudeError("Claude HTTP 403", 403), "auth", id="claude-forbidden"),
    pytest.param(JevError("Jev HTTP 402", 402), "no_credit", id="jev-payment-required"),
    pytest.param(ClaudeError("Claude account has no credit", 402), "no_credit", id="claude-no-credit"),
    pytest.param(JevError("Jev request timed out"), "unreachable", id="timeout"),
    pytest.param(ClaudeError("Claude connection failed"), "unreachable", id="connection-failed"),
    pytest.param(ClaudeError("Claude HTTP 503", 503), "unreachable", id="service-down"),
    pytest.param(JevError("Jev HTTP 429", 429), "degraded", id="rate-limited"),
    pytest.param(ClaudeError("Claude returned invalid JSON"), "degraded", id="bad-answer"),
    pytest.param(ValueError("anything else"), "degraded", id="unknown-error"),
])
def test_a_failure_is_classified_by_its_status_or_its_words(error: Exception, status: str) -> None:
    assert classify(error) == status


@pytest.mark.parametrize("recent, status", [
    pytest.param([], "checking", id="nothing-yet"),
    pytest.param([None], "ok", id="one-success"),
    pytest.param([None] * 9 + ["degraded"], "ok", id="a-single-failure-in-ten"),
    pytest.param(["degraded", "degraded", None, None], "degraded", id="half-failing"),
    pytest.param([None, None, "no_credit"], "no_credit", id="out-of-credit-now"),
    pytest.param(["no_credit", None], "ok", id="recovered"),
    pytest.param([None, "auth"], "auth", id="key-refused-now"),
    pytest.param([None, "unreachable"], "unreachable", id="unreachable-now"),
    pytest.param(["degraded"] * 12 + [None] * 10, "ok", id="old-failures-fall-out-of-the-window"),
])
def test_health_follows_the_recent_calls(recent: list[str | None], status: str) -> None:
    assert judge(recent)["status"] == status


def test_a_service_without_a_key_stays_no_key_whatever_is_recorded() -> None:
    board = HealthBoard({"jev": False, "claude": True})
    board.record("jev", None)
    assert (board.snapshot()["jev"]["status"], board.snapshot()["claude"]["status"]) == ("no_key", "checking")


def test_recording_failures_and_successes_moves_the_status() -> None:
    board = HealthBoard({"jev": True, "claude": True})
    board.record("claude", ClaudeError("Claude account has no credit", 402))
    assert board.snapshot()["claude"]["status"] == "no_credit"
    assert "no credit" in board.snapshot()["claude"]["reason"]
    board.record("claude", None)
    assert board.snapshot()["claude"] == {"status": "ok", "reason": ""}


@pytest.mark.parametrize("raised, status", [
    pytest.param(None, "ok", id="answers"),
    pytest.param(JevError("Jev HTTP 401", 401), "auth", id="refused"),
    pytest.param(JevError("Jev HTTP 402", 402), "no_credit", id="no-credit"),
])
def test_a_probe_records_what_the_call_did(raised: Exception | None, status: str) -> None:
    async def call() -> Any:
        if raised:
            raise raised
        return {}

    board = HealthBoard({"jev": True, "claude": True})
    assert asyncio.run(board.probe("jev", call))["status"] == status
    assert board.snapshot()["jev"]["status"] == status


def test_a_probe_of_a_service_without_a_key_makes_no_call() -> None:
    called: list[bool] = []

    async def call() -> Any:
        called.append(True)

    board = HealthBoard({"jev": False, "claude": True})
    assert asyncio.run(board.probe("jev", call))["status"] == "no_key"
    assert called == []


@pytest.mark.parametrize("statuses, used, text, stopped", [
    pytest.param({"jev": "ok", "claude": "ok"}, ("jev", "claude"), "JEV: OK  CLAUDE: OK", [], id="all-well"),
    pytest.param({"jev": "ok", "claude": "no_credit"}, ("jev", "claude"), "JEV: OK  CLAUDE: NO CREDIT", ["claude"],
                 id="claude-out-of-credit"),
    pytest.param({"jev": "no_key", "claude": "auth"}, ("jev", "claude"), "JEV: NO KEY  CLAUDE: AUTH",
                 ["jev", "claude"], id="both-unusable"),
    pytest.param({"jev": "no_key", "claude": "ok"}, ("claude",), "JEV: OFF  CLAUDE: OK", [], id="unused-service-is-off"),
    pytest.param({"jev": "unreachable", "claude": "degraded"}, ("jev", "claude"), "JEV: UNREACHABLE  CLAUDE: DEGRADED",
                 [], id="shaky-services-do-not-stop-a-run"),
])
def test_banner_and_blocking_only_count_the_services_in_use(statuses: dict[str, str], used: tuple[str, ...],
                                                            text: str, stopped: list[str]) -> None:
    health = {name: {"status": status, "reason": ""} for name, status in statuses.items()}
    assert (banner(health, used), blocking(health, used)) == (text, stopped)
