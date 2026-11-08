"""The AI config read from the environment: defaults, overrides and malformed values."""

import pytest

from tavern.mind.selection import read_ai_config


@pytest.mark.parametrize(
    "values, key, expected",
    [
        pytest.param({}, None, {"typesafe_api_key": None, "model": "jev-latest", "timeout": 8.0,
                                "temperature": 0.25, "answers": False}, id="empty-environment"),
        pytest.param({"TYPESAFE_MODEL": "jev-fast", "AI_TIMEOUT": "12.5", "AI_TEMPERATURE": "0", "AI_ANSWERS": "true"},
                     "secret", {"typesafe_api_key": "secret", "model": "jev-fast", "timeout": 12.5,
                                "temperature": 0.0, "answers": True}, id="every-variable-set"),
        pytest.param({"AI_ANSWERS": ""}, "k", {"typesafe_api_key": "k", "model": "jev-latest", "timeout": 8.0,
                                               "temperature": 0.25, "answers": False}, id="empty-switch-is-default"),
    ],
)
def test_read_ai_config_reads_the_variables(values, key, expected):
    assert read_ai_config(values, key) == expected


@pytest.mark.parametrize(
    "values, name",
    [
        pytest.param({"AI_TIMEOUT": "soon"}, "AI_TIMEOUT", id="timeout-not-a-number"),
        pytest.param({"AI_TEMPERATURE": "warm"}, "AI_TEMPERATURE", id="temperature-not-a-number"),
        pytest.param({"AI_ANSWERS": "maybe"}, "AI_ANSWERS", id="answers-not-a-switch"),
    ],
)
def test_read_ai_config_names_the_malformed_variable(values, name):
    with pytest.raises(ValueError, match=name):
        read_ai_config(values, None)
