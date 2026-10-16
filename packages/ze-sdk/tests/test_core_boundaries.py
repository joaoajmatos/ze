"""ze_sdk is the plugin surface; core and integration packages import the owning package."""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LAYER_GLOBS = ("core/*/*/**/*.py", "integrations/*/**/*.py")
SKIPPED_PARTS = {".venv", "node_modules"}


def _sdk_importers() -> list[str]:
    found: list[str] = []
    scanned = 0
    for pattern in LAYER_GLOBS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            if SKIPPED_PARTS & set(path.relative_to(REPO_ROOT).parts):
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
                    if module.split(".")[0] == "ze_sdk"
                )
    assert scanned, "no core or integration sources found; the globs are stale"
    return found


def test_core_and_integration_packages_never_import_ze_sdk() -> None:
    found = _sdk_importers()
    assert not found, (
        "ze-sdk depends on the core packages, so they must import the owning "
        "package (ze_agents, ze_proactive, ze_memory, ...):\n" + "\n".join(found)
    )
