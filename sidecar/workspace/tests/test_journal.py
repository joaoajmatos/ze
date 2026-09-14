from __future__ import annotations

import json
import time
from uuid import uuid4


def _wait_until(predicate, timeout=2.0, interval=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def test_run_returns_immediately_with_id(sidecar):
    resp = sidecar.post("/run", json={"command": ["sh", "-c", "sleep 0.2"]})
    assert resp.status_code == 200
    run_id = resp.json()["id"]
    assert run_id

    status = sidecar.get(f"/runs/{run_id}").json()
    assert status["status"] == "running"


def test_run_honors_client_supplied_id(sidecar):
    supplied = str(uuid4())
    resp = sidecar.post(
        "/run", json={"command": ["sh", "-c", "echo hi"], "id": supplied}
    )
    assert resp.json()["id"] == supplied


def test_get_run_reflects_terminal_status(sidecar):
    resp = sidecar.post("/run", json={"command": ["sh", "-c", "echo hi"]})
    run_id = resp.json()["id"]

    assert _wait_until(
        lambda: sidecar.get(f"/runs/{run_id}").json()["status"] != "running"
    )
    status = sidecar.get(f"/runs/{run_id}").json()
    assert status["status"] == "succeeded"
    assert status["exit_code"] == 0
    assert "hi" in status["stdout_preview"]


def test_get_run_unknown_id_404(sidecar):
    resp = sidecar.get(f"/runs/{uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


def test_events_stream_replays_then_completes(sidecar):
    resp = sidecar.post(
        "/run", json={"command": ["sh", "-c", "echo one; echo two"]}
    )
    run_id = resp.json()["id"]
    assert _wait_until(
        lambda: sidecar.get(f"/runs/{run_id}").json()["status"] != "running"
    )

    events_resp = sidecar.get(f"/runs/{run_id}/events")
    assert events_resp.status_code == 200
    lines = [json.loads(line) for line in events_resp.text.strip().splitlines() if line]
    assert lines[-1]["type"] == "exit"
    assert lines[-1]["exit_code"] == 0
    stdout_data = "".join(line["data"] for line in lines if line["type"] == "stdout")
    assert "one" in stdout_data and "two" in stdout_data


def test_events_stream_unknown_id_404(sidecar):
    resp = sidecar.get(f"/runs/{uuid4()}/events")
    assert resp.status_code == 404


def test_two_watchers_both_read_same_run(sidecar):
    resp = sidecar.post("/run", json={"command": ["sh", "-c", "echo hi"]})
    run_id = resp.json()["id"]
    assert _wait_until(
        lambda: sidecar.get(f"/runs/{run_id}").json()["status"] != "running"
    )

    first = sidecar.get(f"/runs/{run_id}/events").text
    second = sidecar.get(f"/runs/{run_id}/events").text
    assert first == second
    assert "exit" in first


def test_cancel_in_progress_stops_process(sidecar):
    resp = sidecar.post("/run", json={"command": ["sh", "-c", "sleep 5"]})
    run_id = resp.json()["id"]

    cancel_resp = sidecar.post(f"/runs/{run_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json() == {"ok": True}

    status = sidecar.get(f"/runs/{run_id}").json()
    assert status["status"] == "cancelled"


def test_cancel_already_terminal_409(sidecar):
    resp = sidecar.post("/run", json={"command": ["sh", "-c", "echo hi"]})
    run_id = resp.json()["id"]
    assert _wait_until(
        lambda: sidecar.get(f"/runs/{run_id}").json()["status"] != "running"
    )

    cancel_resp = sidecar.post(f"/runs/{run_id}/cancel")
    assert cancel_resp.status_code == 409
    assert cancel_resp.json()["error"] == "already_terminal"


def test_cancel_unknown_id_404(sidecar):
    resp = sidecar.post(f"/runs/{uuid4()}/cancel")
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


def test_one_slot_invariant_409_names_running_handle(sidecar):
    first = sidecar.post("/run", json={"command": ["sh", "-c", "sleep 5"]})
    first_id = first.json()["id"]

    second = sidecar.post("/run", json={"command": ["sh", "-c", "echo hi"]})
    assert second.status_code == 409
    body = second.json()
    assert body["error"] == "busy"
    assert body["id"] == first_id
    assert body["command"] == ["sh", "-c", "sleep 5"]

    sidecar.post(f"/runs/{first_id}/cancel")


def test_new_run_allowed_after_previous_terminal(sidecar):
    first = sidecar.post("/run", json={"command": ["sh", "-c", "echo hi"]})
    first_id = first.json()["id"]
    assert _wait_until(
        lambda: sidecar.get(f"/runs/{first_id}").json()["status"] != "running"
    )

    second = sidecar.post("/run", json={"command": ["sh", "-c", "echo bye"]})
    assert second.status_code == 200


def test_retention_evicts_oldest_terminal_entry(sidecar):
    import supervisor

    ids = []
    for i in range(supervisor.JOURNAL_RETAIN_TERMINAL + 1):
        resp = sidecar.post("/run", json={"command": ["sh", "-c", f"echo {i}"]})
        run_id = resp.json()["id"]
        ids.append(run_id)
        assert _wait_until(
            lambda rid=run_id: sidecar.get(f"/runs/{rid}").json()["status"] != "running"
        )

    oldest = sidecar.get(f"/runs/{ids[0]}")
    assert oldest.status_code == 404
    newest = sidecar.get(f"/runs/{ids[-1]}")
    assert newest.status_code == 200
