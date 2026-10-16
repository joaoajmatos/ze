import asyncio
import json

import httpx
import pytest

from ze_eval import runner
from ze_eval.runner import collect_tool_calls, turn_label

_PARKED_REPLY = {
    "response": "Delete 'Standup'?",
    "agent_used": "calendar",
    "pending_confirmation": True,
    "tool_calls": [{"tool_name": "delete_event", "gate": "parked", "parked": True}],
}
_APPROVED_REPLY = {
    "response": "Done, I deleted it.",
    "agent_used": "calendar",
    "pending_confirmation": False,
    "tool_calls": [
        {"tool_name": "delete_event", "gate": "approved", "parked": False}
    ],
}


def _run(scenario: dict) -> dict:
    return asyncio.run(runner._run_turns(scenario, "eval-s1", "http://ze", "key"))


class FakeZe:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.replies: dict[str, list[httpx.Response]] = {}

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.replies[request.url.path].pop(0)


@pytest.fixture
def ze_http(monkeypatch) -> FakeZe:
    fake = FakeZe()
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        return real(*args, transport=httpx.MockTransport(fake.handle), **kwargs)

    monkeypatch.setattr(runner.httpx, "AsyncClient", factory)
    return fake


def test_collects_tool_calls_from_every_turn_in_order():
    turns = [
        {
            "turn": 1,
            "prompt": "find the file",
            "result": {"tool_calls": [{"tool_name": "search", "success": True}]},
        },
        {
            "turn": 2,
            "prompt": "email it",
            "result": {
                "tool_calls": [
                    {"tool_name": "send_email", "gate": "parked", "parked": True}
                ],
                "pending_confirmation": True,
            },
        },
    ]

    calls = collect_tool_calls(turns)

    assert [c["tool_name"] for c in calls] == ["search", "send_email"]
    assert [c["turn"] for c in calls] == [1, 2]


def test_collect_skips_turns_without_tool_calls():
    turns = [
        {"turn": 1, "prompt": "hello", "result": {}},
        {
            "turn": 2,
            "prompt": "now search",
            "result": {"tool_calls": [{"tool_name": "search"}]},
        },
    ]

    calls = collect_tool_calls(turns)

    assert [c["tool_name"] for c in calls] == ["search"]
    assert [c["turn"] for c in calls] == [2]


def test_collect_does_not_mutate_the_source_calls():
    original = {"tool_name": "search", "success": True}
    turns = [{"turn": 1, "prompt": "p", "result": {"tool_calls": [original]}}]

    collect_tool_calls(turns)

    assert "turn" not in original


def test_collect_returns_empty_for_no_turns():
    assert collect_tool_calls([]) == []


def test_confirm_turn_posts_to_eval_confirm_with_the_same_session(ze_http):
    ze_http.replies["/eval/chat"] = [httpx.Response(200, json=_PARKED_REPLY)]
    ze_http.replies["/eval/confirm"] = [httpx.Response(200, json=_APPROVED_REPLY)]
    scenario = {"turns": [{"prompt": "delete my 3pm"}, {"confirm": "approve"}]}

    result = _run(scenario)

    chat, confirm = ze_http.requests
    assert chat.url.path == "/eval/chat"
    assert confirm.url.path == "/eval/confirm"
    assert confirm.headers["x-ze-api-key"] == "key"
    assert json.loads(confirm.content) == {"session_id": "eval-s1", "choice": "approve"}
    assert [t["result"]["tool_calls"][0]["gate"] for t in result["turns"]] == [
        "parked",
        "approved",
    ]
    assert result["turns"][1]["confirm"] == "approve"
    assert result["agent_used"] == "calendar"
    assert result["response"] == "Done, I deleted it."


def test_confirm_turn_sends_edits(ze_http):
    ze_http.replies["/eval/chat"] = [httpx.Response(200, json=_PARKED_REPLY)]
    ze_http.replies["/eval/confirm"] = [httpx.Response(200, json=_APPROVED_REPLY)]
    scenario = {
        "turns": [
            {"prompt": "send Ana the notes"},
            {"confirm": "approve", "edits": {"item-1": "Hi Ana"}},
        ]
    }

    _run(scenario)

    assert json.loads(ze_http.requests[1].content) == {
        "session_id": "eval-s1",
        "choice": "approve",
        "edits": {"item-1": "Hi Ana"},
    }


def test_confirm_without_open_confirmation_has_a_clear_error(ze_http):
    ze_http.replies["/eval/chat"] = [httpx.Response(200, json={"response": "hi"})]
    ze_http.replies["/eval/confirm"] = [
        httpx.Response(409, json={"detail": "no pending confirmation"})
    ]
    scenario = {"turns": [{"prompt": "hello"}, {"confirm": "deny"}]}

    with pytest.raises(runner.ConfirmStepError, match="no open confirmation"):
        _run(scenario)


def test_a_second_round_can_be_answered(ze_http):
    ze_http.replies["/eval/chat"] = [httpx.Response(200, json=_PARKED_REPLY)]
    ze_http.replies["/eval/confirm"] = [
        httpx.Response(200, json=_PARKED_REPLY),
        httpx.Response(200, json=_APPROVED_REPLY),
    ]
    scenario = {
        "turns": [
            {"prompt": "do two things"},
            {"confirm": "approve"},
            {"confirm": "approve"},
        ]
    }

    result = _run(scenario)

    assert len(result["turns"]) == 3
    assert [r.url.path for r in ze_http.requests] == [
        "/eval/chat",
        "/eval/confirm",
        "/eval/confirm",
    ]


@pytest.mark.parametrize(
    "turn",
    [
        {"confirm": "maybe"},
        {"prompt": "x", "confirm": "approve"},
        {},
        {"prompt": "x", "edits": {"a": "b"}},
    ],
)
def test_bad_turns_are_rejected_before_any_request(ze_http, turn):
    with pytest.raises(ValueError):
        _run({"turns": [turn]})

    assert ze_http.requests == []


def test_turn_label_names_the_confirm_step():
    assert turn_label({"turn": 2, "prompt": None, "confirm": "deny"}) == "[confirm: deny]"
    assert turn_label({"turn": 1, "prompt": "hello"}) == "hello"
