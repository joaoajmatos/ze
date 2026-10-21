import re
from pathlib import Path

import pytest
from conftest import load_process_module

REPO = Path(__file__).parents[2]
SKILLS = sorted((REPO / ".claude" / "skills").glob("ze-*/SKILL.md"))
MAKEFILE = (REPO / "Makefile").read_text()
SIDE_EFFECTING = {"ze-land-floor", "ze-recruit", "ze-pause", "ze-continue"}


def frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    assert match, "SKILL.md needs --- frontmatter"
    fields = dict(
        line.split(": ", 1) for line in match.group(1).splitlines() if ": " in line
    )
    return fields, match.group(2)


def test_there_are_process_skills():
    assert {p.parent.name for p in SKILLS} >= {
        "ze-land-floor",
        "ze-recruit",
        "ze-request-review",
        "ze-web-verify",
    }


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parent.name)
def test_skill_is_well_formed(path):
    fields, body = frontmatter(path.read_text())
    name = path.parent.name
    assert fields["name"] == name
    assert len(name) <= 64 and re.fullmatch(r"[a-z0-9-]+", name)
    description = fields["description"]
    assert len(description) <= 1024
    assert "Use when" in description, "description needs a 'Use when' clause"
    assert not re.match(r"(I|You|We)\b", description), (
        "write the description in the third person"
    )
    assert len(body.splitlines()) < 500
    if name in SIDE_EFFECTING:
        assert fields.get("disable-model-invocation") == "true", (
            f"{name} has side effects"
        )
    else:
        assert "disable-model-invocation" not in fields


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parent.name)
def test_skill_references_exist(path):
    text = path.read_text()
    for script in set(re.findall(r"scripts/process/[\w./-]+\.(?:sh|py)", text)):
        assert (REPO / script).exists(), f"{script} is referenced but missing"
    for span in re.findall(r"`([^`]+)`", text):
        match = re.match(r"make ([a-z][\w-]*)", span)
        if match:
            assert re.search(rf"^{re.escape(match.group(1))}:", MAKEFILE, re.M), (
                f"make target {match.group(1)} missing"
            )


def test_every_model_invoked_skill_has_eval_tasks():
    skill_eval = load_process_module("skill_eval")
    model_invoked = {
        p.parent.name
        for p in SKILLS
        if "disable-model-invocation" not in frontmatter(p.read_text())[0]
    }
    assert {f.stem for f in skill_eval.EVALS.glob("*.json")} == model_invoked
    for f in skill_eval.EVALS.glob("*.json"):
        assert skill_eval.validate(skill_eval.load(f)) == []


def test_eval_grading_and_split():
    skill_eval = load_process_module("skill_eval")
    transcript = [
        {
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Skill",
                        "input": {"skill": "ze-web-verify"},
                    }
                ]
            }
        },
        {
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Bash",
                        "input": {"command": "make process-ready PORTAL_SHOT=a.png"},
                    }
                ]
            }
        },
    ]
    assert skill_eval.triggered(transcript, "ze-web-verify")
    assert not skill_eval.triggered(transcript, "ze-recruit")
    judges = [
        {"op": "cmd_matches", "match": "process-ready.*PORTAL_SHOT"},
        {"op": "not_cmd_matches", "match": "git push"},
        {"op": "tool_called", "tool": "Bash", "match": "process-ready"},
    ]
    assert all(ok for _, ok in skill_eval.grade(transcript, judges))
    assert not skill_eval.grade(
        transcript, [{"op": "not_cmd_matches", "match": "process-ready"}]
    )[0][1]
    queries = [{"query": f"q{i}", "should_trigger": True} for i in range(100)]
    train, test = skill_eval.split(queries)
    assert 50 <= len(train) <= 70 and len(train) + len(test) == 100
    assert skill_eval.accuracy([(True, True), (False, True)]) == 0.5


def test_run_refuses_without_the_spend_flag():
    skill_eval = load_process_module("skill_eval")
    assert skill_eval.main(["--run", "ze-web-verify"]) == 2


def test_speckit_hooks_point_at_existing_skills():
    yaml = pytest.importorskip("yaml")
    hooks = yaml.safe_load((REPO / ".specify" / "extensions.yml").read_text())["hooks"]
    for entries in hooks.values():
        for hook in entries:
            skill = hook["command"].replace(".", "-")
            assert (REPO / ".claude" / "skills" / skill / "SKILL.md").exists(), skill
            assert hook["optional"] is False


def test_settings_hooks_run_existing_scripts_and_keep_the_rest():
    import json

    settings = json.loads((REPO / ".claude" / "settings.json").read_text())
    assert "permissions" in settings and "mcpServers" in settings
    commands = [
        h["command"]
        for group in settings["hooks"].values()
        for entry in group
        for h in entry["hooks"]
    ]
    assert commands
    for command in commands:
        script = re.search(r"scripts/process/hooks/\w+\.py", command).group(0)
        assert (REPO / script).exists(), script
