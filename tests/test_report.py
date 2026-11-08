"""The evening report: what `make evening` writes as metrics.json, assembled from a finished evening."""

from test_lockstep import evening, preferring

from tavern.adapters.claude import HAIKU_5_5
from tavern.evening.report import evening_report
from tavern.evening.story_score import WEIGHTS, story_moments, story_score

KEYS = ["run", "game_seconds", "guests", "departures", "completed", "conversations", "quarrels", "decisions",
        "errors", "cost", "stuck", "intentions", "repetition", "choice", "responses", "aims", "projects",
        "invitations", "goals", "goal_kinds", "chased", "promises", "attention", "conversation", "news", "dice",
        "sleep", "drink", "speeches", "stage", "giving", "manners", "closing", "ailment", "fights", "story", "bar",
        "writer"]


def report_of_a_short_evening(run: dict[str, object]) -> tuple[dict[str, object], object]:
    """Play a two-guest offline evening and report on it."""
    played, world = evening(preferring("wait"), limit=20.0)
    tariffs = {"turn": HAIKU_5_5, "intention": HAIKU_5_5, "stage": HAIKU_5_5}
    return evening_report(played, world, [], run, 3.0, 30.0, tariffs, HAIKU_5_5), played


def test_report_has_the_documented_keys_in_order() -> None:
    report, _ = report_of_a_short_evening({"mode": "local"})
    assert list(report) == KEYS


def test_report_story_is_the_score_of_the_evening_events() -> None:
    report, played = report_of_a_short_evening({"mode": "local"})
    assert report["story"] == story_score(story_moments(played.events), WEIGHTS)


def test_report_run_is_the_mapping_passed_in() -> None:
    run = {"mode": "local", "seed": 3}
    report, _ = report_of_a_short_evening(run)
    assert report["run"] == run
