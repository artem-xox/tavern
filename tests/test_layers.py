"""The layer rule: the domain packages never import an adapter, the server, or the outside world."""

import ast
from pathlib import Path

import pytest

TAVERN = Path(__file__).resolve().parents[1] / "backend" / "tavern"
DOMAIN = ("hall", "body", "social", "mind", "evening")
# Adapters and the shell are reached through ports; these are the outside world itself.
FORBIDDEN = ("tavern.adapters", "tavern.server", "tavern.app", "fastapi", "httpx", "psycopg", "anthropic", "os")


def forbidden_imports(source: str) -> list[str]:
    """List the forbidden modules a source file imports, wherever it does so."""
    found = []
    for node in ast.walk(ast.parse(source)):
        modules = ([alias.name for alias in node.names] if isinstance(node, ast.Import) else
                   [node.module or ""] if isinstance(node, ast.ImportFrom) and node.level == 0 else [])
        found += [module for module in modules
                  if any(module == name or module.startswith(name + ".") for name in FORBIDDEN)]
    return found


@pytest.mark.parametrize("source, expected", [
    pytest.param("", [], id="empty-file"),
    pytest.param("import json\nfrom tavern.hall.room import find_object\n", [], id="core-imports-only"),
    pytest.param("from tavern.adapters.jev import evaluate_actions\n", ["tavern.adapters.jev"], id="adapter"),
    pytest.param("import os\n", ["os"], id="environment"),
    pytest.param("import os.path\n", ["os.path"], id="submodule-of-environment"),
    pytest.param("from fastapi import FastAPI\nimport httpx\n", ["fastapi", "httpx"], id="several"),
    pytest.param("def f():\n    from tavern.server.api import create_app\n", ["tavern.server.api"], id="inside-a-function"),
    pytest.param("import osmosis\nfrom tavern.adapters_not import x\n", [], id="names-that-only-start-alike"),
])
def test_forbidden_imports_are_found_wherever_they_stand(source: str, expected: list[str]) -> None:
    assert forbidden_imports(source) == expected


@pytest.mark.parametrize("package", [pytest.param(name, id=name) for name in DOMAIN])
def test_a_domain_package_imports_no_adapter_shell_or_environment(package: str) -> None:
    modules = sorted((TAVERN / package).glob("*.py"))
    assert modules, f"{package} holds no modules"
    violations = {path.name: found for path in modules if (found := forbidden_imports(path.read_text()))}
    assert violations == {}


def test_every_module_belongs_to_a_package_but_the_launch_wiring() -> None:
    loose = sorted(path.name for path in TAVERN.glob("*.py") if path.name not in ("__init__.py", "app.py"))
    assert loose == []
