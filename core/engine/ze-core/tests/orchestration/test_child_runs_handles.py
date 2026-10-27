from __future__ import annotations

from unittest.mock import MagicMock

from ze_core.orchestration.child_runs import runtime_handles


def _config() -> dict:
    embedder = MagicMock()
    return {
        "configurable": {
            "reporter": "reporter",
            "identity_builder": "identity",
            "abort_token": "abort",
            "embedder": embedder,
            "token_sink": "tokens",
            "tool_sink": "tools",
            "script_runner": "scripts",
        }
    }


def test_runtime_handles_reads_every_handle_from_the_turn_config() -> None:
    config = _config()
    handles = runtime_handles(config, stream=True)
    assert handles.reporter == "reporter"
    assert handles.identity_builder == "identity"
    assert handles.abort_token == "abort"
    assert handles.embed_fn is config["configurable"]["embedder"].encode_query
    assert handles.token_sink == "tokens"
    assert handles.tool_sink == "tools"
    assert handles.script_runner == "scripts"


def test_only_a_streaming_run_gets_the_token_sink() -> None:
    assert runtime_handles(_config(), stream=False).token_sink is None


def test_missing_handles_are_none() -> None:
    handles = runtime_handles({"configurable": {}}, stream=True)
    assert handles.embed_fn is None and handles.reporter is None
