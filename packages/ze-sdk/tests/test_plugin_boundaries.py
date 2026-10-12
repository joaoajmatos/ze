"""Plugin code reaches the engine only through ze_sdk.*; see AGENTS.md "Imports"."""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FORBIDDEN_ROOTS = {"ze_core", "ze_api", "ze_plugin"}
SEED_FORBIDDEN_ROOTS = {"ze_api"}


def _violations(files: list[Path], forbidden: set[str], *, forbid_ze_memory: bool) -> list[str]:
    found: list[str] = []
    for path in files:
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules = [node.module]
            else:
                continue
            for module in modules:
                root = module.split(".")[0]
                bad = root in forbidden or (
                    forbid_ze_memory and root == "ze_memory"
                )
                if bad:
                    found.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} imports {module}")
    return sorted(found)


def _plugin_sources() -> list[Path]:
    files = []
    for path in (REPO_ROOT / "plugins").glob("*/ze_*/**/*.py"):
        if "tests" in path.relative_to(REPO_ROOT).parts:
            continue
        files.append(path)
    return files


def test_plugins_import_only_through_ze_sdk() -> None:
    files = _plugin_sources()
    assert files, "no plugin sources found; the glob is stale"
    found = _violations(files, FORBIDDEN_ROOTS, forbid_ze_memory=True)
    assert not found, "plugin code must import via ze_sdk.*:\n" + "\n".join(found)


def test_ze_seed_does_not_import_the_api_app() -> None:
    files = list((REPO_ROOT / "core/ops/ze-seed/ze_seed").rglob("*.py"))
    assert files, "no ze-seed sources found; the path is stale"
    found = _violations(files, SEED_FORBIDDEN_ROOTS, forbid_ze_memory=False)
    assert not found, "apps are leaves; ze-seed must not import ze_api:\n" + "\n".join(found)
