"""Stage numbers: which number a guest on the stage performs, at whom, and the words when no writer answers."""

from typing import Any

import pytest

from tavern.social.conversation import DISLIKED
from tavern.social.numbers import NUMBERS, ROASTED_AT, choose_number, scripted_number

SECRET = "The tower was never finished."


def performer(opinions: dict[str, float] | None = None, drunk: float = 0.0, secret: str | None = None,
              memory: tuple[dict[str, Any], ...] = ()) -> dict[str, Any]:
    """Ada, a showman with opinions of the others, drink in her, perhaps a secret, and what she remembers."""
    relations = {other: {"name": other.title(), "opinion": opinion, "familiarity": "acquaintance", "knows_name": True}
                 for other, opinion in (opinions or {}).items()}
    card = {"persona": "A loud showman", "catchphrases": ["Tremendous!", "Believe me."],
            **({"secret": secret} if secret else {})}
    return {"id": "ada", "name": "Ada", "relations": relations, "thoughts": [], "drunkenness": drunk, "card": card,
            "memory": list(memory)}


CONFESSED = {"time": 10.0, "actor_id": "ada", "type": "gave_speech", "message": "Ada confessed", "number": "confession"}


@pytest.mark.parametrize("ada, present, expected", [
    pytest.param(performer(), [], ("pitch", None), id="an-empty-room-hears-a-pitch"),
    pytest.param(performer(), ["bea"], ("pitch", None), id="nobody-liked-or-loathed"),
    pytest.param(performer({"bea": -30.0}), ["bea"], ("roast", "bea"), id="a-rival-present-is-roasted"),
    pytest.param(performer({"bea": -30.0}), [], ("pitch", None), id="an-absent-rival-is-not"),
    pytest.param(performer({"bea": -30.0, "cid": -60.0}), ["bea", "cid"], ("roast", "cid"), id="the-most-disliked"),
    pytest.param(performer({"bea": -40.0, "cid": -40.0}), ["cid", "bea"], ("roast", "bea"), id="a-tie-goes-to-the-lower-id"),
    pytest.param(performer({"bea": 40.0}, drunk=0.3), ["bea"], ("toast", "bea"), id="the-tipsy-toast-a-friend"),
    pytest.param(performer({"bea": 40.0}), ["bea"], ("pitch", None), id="the-sober-do-not-toast"),
    pytest.param(performer({"bea": 20.0}, drunk=0.3), ["bea"], ("pitch", None), id="a-mere-acquaintance-is-no-toast"),
    pytest.param(performer({"bea": 40.0, "cid": -30.0}, drunk=0.3), ["bea", "cid"], ("roast", "cid"),
                 id="a-roast-before-a-toast"),
    pytest.param(performer({"bea": -30.0}, drunk=0.5, secret=SECRET), ["bea"], ("confession", None),
                 id="the-drunk-confess-first"),
    pytest.param(performer(drunk=0.3, secret=SECRET), [], ("pitch", None), id="the-tipsy-keep-their-secret"),
    pytest.param(performer(drunk=0.5, secret=SECRET, memory=(CONFESSED,)), [], ("pitch", None),
                 id="one-confession-a-night"),
    pytest.param(performer({"ada": -50.0}), ["ada"], ("pitch", None), id="never-at-themselves"),
])
def test_the_number_a_performer_gives_and_at_whom(ada: dict[str, Any], present: list[str],
                                                  expected: tuple[str, str | None]) -> None:
    assert choose_number(ada, present, now=20.0) == expected


def test_every_number_says_what_the_writer_is_asked_for() -> None:
    assert set(NUMBERS) == {"toast", "roast", "pitch", "confession"} and all(item.brief for item in NUMBERS.values())


@pytest.mark.parametrize("kind, target, present", [
    pytest.param("toast", "Bea", ["Bea"], id="a-toast-names-its-target"),
    pytest.param("roast", "Bea", ["Bea"], id="a-roast-names-its-target"),
    pytest.param("pitch", None, ["Tremendous!"], id="a-pitch-ends-on-a-catchphrase"),
    pytest.param("confession", None, [], id="a-confession-hints-without-telling"),
])
def test_the_scripted_words_of_a_number(kind: str, target: str | None, present: list[str]) -> None:
    # The fallback when no writer answers: aimed words, never the guest's inner thought or their secret.
    lines = scripted_number(performer(secret=SECRET), kind, target, roll=0.0)
    words = " ".join(lines)
    assert (2 <= len(lines) <= 3, [item for item in present if item not in words], SECRET in words) == (True, [], False)


def test_a_roast_takes_the_dislike_an_insult_takes() -> None:
    assert ROASTED_AT == DISLIKED
