import importlib

from ze_agents.registry import get_registered_agents

from tests.support.agent_modules import ALL_AGENT_MODULE_PATHS


def test_agents_registered_via_agent_decorator():
    for path in ALL_AGENT_MODULE_PATHS:
        importlib.import_module(path)
    agents = get_registered_agents()
    assert "research" in agents
    assert "companion" in agents
    assert "calendar" in agents
    assert "messenger" in agents
    assert "workflow" in agents
    assert "goals" in agents
    assert "priority" in agents
    research = agents["research"]
    assert getattr(research, "description", "").strip()
    assert getattr(research, "model", "")


def test_container_hands_shared_system_one_client_to_skill_matcher():
    import ast
    from pathlib import Path

    import ze_api.container as container_module

    tree = ast.parse(Path(container_module.__file__).read_text())
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "build_skill_matcher"
    ]
    assert len(calls) == 1
    kwargs = {kw.arg: ast.unparse(kw.value) for kw in calls[0].keywords}
    assert kwargs["system_one_client"] == "shared.system_one_client"


def test_shipped_config_builds_a_disabled_skills_surface():
    from pathlib import Path

    import yaml
    from ze_skills.bootstrap import build_skill_matcher

    config_path = Path(__file__).resolve().parents[1] / "config" / "config.yaml"

    class _Settings:
        config = yaml.safe_load(config_path.read_text())

    client = object()
    matcher = build_skill_matcher(object(), object(), _Settings(), client)

    assert matcher._system_one is client
    surface = matcher._surface
    assert not surface.enabled and not surface.calibrated
    assert surface.choice_trust is None and surface.needs_skill_hold is None
