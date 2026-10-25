"""Vucic and Sobchak join the lineup with distinct loyalties and rivalries."""

import json
from pathlib import Path

import pytest

from tavern.adapters.characters import load_catalog
from tavern.evening.lineup import casts_public, lineup_scenario

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("guest", [
    pytest.param("vucic", id="vucic"),
    pytest.param("sobchak", id="sobchak"),
])
def test_new_political_guest_is_offered_on_the_lineup_screen(guest: str) -> None:
    catalog = load_catalog(ROOT / "characters")
    template = json.loads((ROOT / "data/scenarios/guests.json").read_text())
    offered = casts_public(catalog, {"guests": template})[0]["characters"]
    assert guest in {item["id"] for item in offered}


@pytest.mark.parametrize("holder, toward, kind", [
    pytest.param("sobchak", "putin", "adored", id="sobchak-flatters-her-patron"),
    pytest.param("putin", "sobchak", "looked down on", id="putin-indulges-sobchak"),
    pytest.param("vucic", "putin", "admired", id="vucic-courts-putin"),
    pytest.param("putin", "vucic", "looked down on", id="putin-distrusts-two-chairs"),
    pytest.param("vucic", "trump", "disliked", id="vucic-resents-trumps-bargains"),
    pytest.param("trump", "vucic", "looked down on", id="trump-patronises-vucic"),
    pytest.param("sobchak", "trump", "disliked", id="sobchak-needles-trump"),
    pytest.param("trump", "sobchak", "looked down on", id="trump-dismisses-the-interviewer"),
    pytest.param("sobchak", "vucic", "well known", id="sobchak-knows-her-interviewee"),
    pytest.param("vucic", "sobchak", "well known", id="vucic-knows-the-interviewer"),
])
def test_political_loyalties_reach_the_evening(holder: str, toward: str, kind: str) -> None:
    catalog = load_catalog(ROOT / "characters")
    template = json.loads((ROOT / "data/scenarios/guests.json").read_text())
    evening = lineup_scenario({"guests": template}, catalog, "guests", [holder, toward], 5)
    guest = next(item for item in evening.guests if item["id"] == holder)
    assert next(tie["kind"] for tie in guest["ties"] if tie["with"] == toward) == kind
