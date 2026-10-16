"""ze_sdk is the plugin surface; core and integration packages import the owning package.

ze_core is the engine; only ze-core and ze-seed (which reads engine message types) may import it.
"""

import ast
import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LAYER_GLOBS = ("core/*/*/**/*.py", "integrations/*/**/*.py")
SKIPPED_PARTS = {".venv", "node_modules"}
ENGINE_CONSUMERS = {"ze-core", "ze-seed"}


def _importers(root: str, *, source_only: bool = False) -> list[str]:
    found: list[str] = []
    scanned = 0
    for pattern in LAYER_GLOBS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            parts = path.relative_to(REPO_ROOT).parts
            if SKIPPED_PARTS & set(parts):
                continue
            if source_only and ("tests" in parts or ENGINE_CONSUMERS & set(parts)):
                continue
            scanned += 1
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    modules = [node.module]
                else:
                    continue
                found.extend(
                    f"{path.relative_to(REPO_ROOT)}:{node.lineno} imports {module}"
                    for module in modules
                    if module.split(".")[0] == root
                )
    assert scanned, "no core or integration sources found; the globs are stale"
    return found


def test_core_and_integration_packages_never_import_ze_sdk() -> None:
    found = _importers("ze_sdk")
    assert not found, (
        "ze-sdk depends on the core packages, so they must import the owning "
        "package (ze_agents, ze_proactive, ze_memory, ...):\n" + "\n".join(found)
    )


def test_core_and_integration_packages_do_not_import_the_engine() -> None:
    found = _importers("ze_core", source_only=True)
    assert not found, (
        "ze-api injects engine behavior into core packages; they must not import ze_core:\n"
        + "\n".join(found)
    )


def _dependency_graph() -> dict[str, set[str]]:
    """Edges from [project].dependencies only; optional and dev groups are not hard edges."""
    manifests = [
        path
        for pattern in ("*/*/pyproject.toml", "*/*/*/pyproject.toml")
        for path in REPO_ROOT.glob(pattern)
        if not SKIPPED_PARTS & set(path.relative_to(REPO_ROOT).parts)
    ]
    declared: dict[str, set[str]] = {}
    for path in manifests:
        project = tomllib.loads(path.read_text()).get("project")
        if project:
            declared[project["name"]] = {
                re.split(r"[<>=\[;~! ]", dep)[0] for dep in project.get("dependencies", [])
            }
    return {name: deps & declared.keys() for name, deps in declared.items()}


def _cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    found: list[list[str]] = []
    state: dict[str, int] = {}
    path: list[str] = []

    def visit(node: str) -> None:
        state[node] = 1
        path.append(node)
        for dep in sorted(graph[node]):
            if state.get(dep) == 1:
                found.append(path[path.index(dep) :] + [dep])
            elif dep not in state:
                visit(dep)
        path.pop()
        state[node] = 2

    for node in sorted(graph):
        if node not in state:
            visit(node)
    return found


def test_cycle_finder_reports_a_loop() -> None:
    assert _cycles({"a": {"b"}, "b": {"a"}, "c": {"a"}}) == [["a", "b", "a"]]
    assert _cycles({"a": {"b"}, "b": set()}) == []


def test_declared_workspace_dependencies_have_no_cycles() -> None:
    graph = _dependency_graph()
    assert "ze-agents" in graph, "no workspace manifests found; the globs are stale"
    cycles = _cycles(graph)
    assert not cycles, "ze-* dependency cycles:\n" + "\n".join(" -> ".join(c) for c in cycles)
