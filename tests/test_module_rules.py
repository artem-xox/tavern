"""The module rules of AGENTS.md: a one-line docstring, a domain name, a length that only shrinks."""

import ast
import re
from collections.abc import Mapping
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TAVERN = ROOT / "backend" / "tavern"
CLIENT = ROOT / "frontend" / "src"
# Bucket names say nothing about what a module owns (AGENTS.md, Navigability).
BANNED_WORDS = frozenset({"util", "utils", "helper", "helpers", "common", "manager", "managers", "base"})
LINE_LIMIT = 400
# Files already past the limit, held at their exact size. Lower a cap in the commit that shrinks its
# file and drop it at 400 or under; re-key it when its file moves; never raise or add one (AGENTS.md, Extending).
CAPS = {
    "backend/tavern/adapters/jev.py": 436,
    "backend/tavern/evening/scenario.py": 401,
    "backend/tavern/hall/lifecycle.py": 417,
    "backend/tavern/mind/haiku_turns.py": 413,
    "backend/tavern/mind/intentions.py": 406,
    "backend/tavern/mind/local_policy.py": 447,
    "backend/tavern/mind/options.py": 402,
    "backend/tavern/mind/turn_prompt.py": 505,
    "backend/tavern/social/invitations.py": 461,
    "backend/tavern/social/scenes.py": 418,
    "backend/tavern/social/thoughts.py": 413,
    "frontend/src/types.ts": 566,
}


def module_summary(source: str) -> str:
    """The first line of a module's docstring, or an empty string when it opens without one."""
    docstring = ast.get_docstring(ast.parse(source)) or ""
    return docstring.split("\n", 1)[0].strip()


def banned_words(stem: str) -> list[str]:
    """The bucket words among the parts of a file name split at `_`, `-` and camelCase humps.

    A run-together name (`baseview`) has no parts to split, so it passes: review catches it.
    """
    parts = re.split(r"[_-]", re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", stem).lower())
    return [part for part in parts if part in BANNED_WORDS]


def over_cap(lengths: Mapping[str, int], caps: Mapping[str, int], limit: int) -> dict[str, int]:
    """The files longer than their cap, or than the limit when they have none, with their length."""
    return {path: length for path, length in lengths.items() if length > caps.get(path, limit)}


def stale_caps(lengths: Mapping[str, int], caps: Mapping[str, int], limit: int) -> dict[str, int | None]:
    """The caps that no longer hold their file's exact length, with that length (None: no such file).

    A cap equal to the length is what makes it a ratchet: a file that shrank must lower its cap, so it
    can never regrow to the old size; one at or under the limit must leave the list.
    """
    return {path: lengths.get(path) for path, cap in caps.items() if lengths.get(path) != cap or cap <= limit}


def sources(root: Path, pattern: str) -> list[Path]:
    """Every file under a root matching a glob pattern, in path order."""
    return sorted(root.rglob(pattern))


@pytest.mark.parametrize("source, expected", [
    pytest.param("", "", id="empty-file"),
    pytest.param('"""What it owns."""\nimport json\n', "What it owns.", id="one-line"),
    pytest.param('"""What it owns.\n\nMore detail.\n"""\n', "What it owns.", id="first-line-of-several"),
    pytest.param('# a comment\n"""What it owns."""\n', "What it owns.", id="after-a-comment"),
    pytest.param('import json\n"""Too late."""\n', "", id="after-code"),
    pytest.param('"""   """\n', "", id="blank"),
    pytest.param("x = 1\n", "", id="no-docstring"),
])
def test_module_summary_is_the_first_line_of_the_opening_docstring(source: str, expected: str) -> None:
    assert module_summary(source) == expected


@pytest.mark.parametrize("source", [
    pytest.param("def (", id="broken-syntax"),
    pytest.param('"""unclosed\n', id="unclosed-docstring"),
])
def test_module_summary_rejects_a_source_that_does_not_parse(source: str) -> None:
    with pytest.raises(SyntaxError):
        module_summary(source)


@pytest.mark.parametrize("stem, expected", [
    pytest.param("", [], id="empty"),
    pytest.param("utils", ["utils"], id="bucket"),
    pytest.param("string_helpers", ["helpers"], id="bucket-suffix"),
    pytest.param("base_store", ["base"], id="bucket-prefix"),
    pytest.param("common_util", ["common", "util"], id="two-buckets"),
    pytest.param("util_util", ["util", "util"], id="duplicate"),
    pytest.param("string-helpers", ["helpers"], id="hyphen"),
    pytest.param("baseStore", ["base"], id="camel-case"),
    pytest.param("JSONHelpers", ["helpers"], id="acronym-camel-case"),
    pytest.param("Utils", ["utils"], id="capitalised"),
    pytest.param("database", [], id="bucket-inside-a-word"),
    pytest.param("baseview", [], id="run-together-passes"),
    pytest.param("story_score", [], id="domain-name"),
])
def test_banned_words_are_whole_parts_of_a_name(stem: str, expected: list[str]) -> None:
    assert banned_words(stem) == expected


@pytest.mark.parametrize("lengths, caps, expected", [
    pytest.param({}, {}, {}, id="no-files"),
    pytest.param({"a.py": 400}, {}, {}, id="at-the-limit"),
    pytest.param({"a.py": 401}, {}, {"a.py": 401}, id="new-file-past-the-limit"),
    pytest.param({"a.py": 450}, {"a.py": 450}, {}, id="at-its-cap"),
    pytest.param({"a.py": 451}, {"a.py": 450}, {"a.py": 451}, id="grown-past-its-cap"),
    pytest.param({"a.py": 120}, {"a.py": 450}, {}, id="shrunk-under-the-limit"),
    pytest.param({"a.py": 401, "b.py": 10}, {}, {"a.py": 401}, id="only-the-long-one"),
])
def test_a_file_may_not_outgrow_its_cap_or_the_limit(lengths: dict[str, int], caps: dict[str, int],
                                                     expected: dict[str, int]) -> None:
    assert over_cap(lengths, caps, limit=400) == expected


@pytest.mark.parametrize("lengths, caps, expected", [
    pytest.param({}, {}, {}, id="no-caps"),
    pytest.param({"a.py": 450}, {"a.py": 450}, {}, id="exact"),
    pytest.param({"a.py": 440}, {"a.py": 450}, {"a.py": 440}, id="shrunk-cap-not-lowered"),
    pytest.param({"a.py": 451}, {"a.py": 450}, {"a.py": 451}, id="grown"),
    pytest.param({"a.py": 400}, {"a.py": 400}, {"a.py": 400}, id="at-the-limit-leaves-the-list"),
    pytest.param({}, {"a.py": 450}, {"a.py": None}, id="file-gone"),
    pytest.param({"a.py": 450, "b.py": 10}, {"a.py": 450}, {}, id="uncapped-file-ignored"),
])
def test_a_cap_holds_its_file_exact_length_above_the_limit(lengths: dict[str, int], caps: dict[str, int],
                                                           expected: dict[str, int | None]) -> None:
    assert stale_caps(lengths, caps, limit=400) == expected


def test_every_backend_module_opens_with_a_docstring() -> None:
    modules = sources(TAVERN, "*.py")
    assert modules, "backend/tavern holds no modules"
    missing = [str(path.relative_to(ROOT)) for path in modules if not module_summary(path.read_text())]
    assert missing == []


def test_no_source_file_has_a_bucket_name() -> None:
    files = sources(TAVERN, "*.py") + sources(CLIENT, "*.ts")
    assert files, "no source files found"
    named = {str(path.relative_to(ROOT)): found for path in files if (found := banned_words(path.stem))}
    assert named == {}


def source_lengths() -> dict[str, int]:
    """The line count of every source file, keyed by its path from the repository root."""
    files = sources(TAVERN, "*.py") + sources(CLIENT, "*.ts")
    return {str(path.relative_to(ROOT)): len(path.read_text().splitlines()) for path in files}


def test_no_source_file_outgrows_its_cap() -> None:
    assert over_cap(source_lengths(), CAPS, LINE_LIMIT) == {}


def test_every_cap_holds_its_file_exact_length() -> None:
    assert stale_caps(source_lengths(), CAPS, LINE_LIMIT) == {}
