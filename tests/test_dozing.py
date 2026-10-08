"""Dozing: what counts as asleep, who may nod off, and how a nap starts and ends."""

from typing import Any

import pytest

from tavern.body.dozing import asleep


@pytest.mark.parametrize("action, expected", [
    pytest.param(None, False, id="no-action"),
    pytest.param({"id": "sit", "verb": "sit", "target_id": "west"}, False, id="sitting"),
    pytest.param({"id": "drink", "verb": "drink", "target_id": None}, False, id="drinking"),
    pytest.param({"id": "doze", "verb": "doze", "target_id": None}, True, id="dozing"),
])
def test_only_a_nap_is_asleep(action: dict[str, Any] | None, expected: bool) -> None:
    assert asleep({"action": action}) is expected
