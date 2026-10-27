import json

from conftest import load_process_module

metrics = load_process_module("metrics")


def write_floor(root, name, verdicts, state=""):
    d = root / name
    (d / "reviews").mkdir(parents=True)
    for i, v in enumerate(verdicts):
        (d / "reviews" / f"r{i}.json").write_text(json.dumps({"verdict": v}))
    if state:
        (d / "state").mkdir()
        (d / "state" / "agent.md").write_text(state)
    return d


def test_review_rounds_and_first_pass(tmp_path):
    d = write_floor(
        tmp_path, "206-x", ["APPROVE", "CHANGES", "APPROVE", "APPROVE", None]
    )
    s = metrics.floor_stats(d)
    assert s["reviews"] == 4
    assert s["changes"] == 1
    assert s["first_pass"] == 0.67


def test_advisor_calls_counted_only_under_heading(tmp_path):
    state = (
        "**Now** proceed with T1 followed\n"
        "**Advisor**\n"
        "- T3 · cache key choice · proceed · followed\n"
        "- T4 · migration order · change course · overrode\n"
        "**Gates** ok\n"
    )
    d = write_floor(tmp_path, "200-y", ["APPROVE"], state)
    s = metrics.floor_stats(d)
    assert s["advisor"] == 2
    assert s["followed"] == 0.5


def test_empty_root_reports_nothing(tmp_path, capsys):
    assert metrics.main(["--root", str(tmp_path)]) == 0
    assert "no archived floors" in capsys.readouterr().out
