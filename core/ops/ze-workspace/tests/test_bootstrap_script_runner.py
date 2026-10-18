from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from ze_workspace.bootstrap import build_workspace_stack
from ze_workspace.script_learning import ScriptLearning
from ze_workspace.scripts import WorkspaceScriptRunner


def _settings(*, token: str = "tok", url: str = "http://sidecar:8080"):
    return SimpleNamespace(
        config={},
        workspace_service_url=url,
        workspace_api_token=token,
        workspace_timeout_seconds=None,
    )


def _build(settings, **kwargs):
    return build_workspace_stack(SimpleNamespace(pool=MagicMock()), settings, **kwargs)


def test_runner_when_the_sidecar_is_configured():
    stack = _build(_settings())
    assert isinstance(stack.script_runner, WorkspaceScriptRunner)
    assert stack.script_runner._client is stack.client


def test_no_runner_without_a_token_or_url():
    assert _build(_settings(token="")).script_runner is None
    assert _build(_settings(url="")).script_runner is None


def test_learning_needs_the_action_store_and_the_admission_service():
    assert _build(_settings()).script_runner._learning is None
    assert (
        _build(_settings(), action_record_store=MagicMock()).script_runner._learning
        is None
    )
    assert (
        _build(_settings(), procedure_admission=MagicMock()).script_runner._learning
        is None
    )
    both = _build(
        _settings(), action_record_store=MagicMock(), procedure_admission=MagicMock()
    )
    assert isinstance(both.script_runner._learning, ScriptLearning)
