import tomllib
from pathlib import Path

from conftest import PROCESS, load_process_module

pausectl = load_process_module("pausectl")
ROLES = tomllib.loads((PROCESS / "roles.toml").read_text())

LIST = """You:
  - name: "Claude Code", maestro: true

Connected agents:
  - name: "Gauge", role: "Reviewer", floor: "Ground"
    ⎿ agent: "Socket"
  - name: "Byline", floor: "Ground"
  - name: "Socket", floor: "191b", status: "not running"
    ⎿ portal: "191b Web" - url: http://127.0.0.1:5200

Connected portals (use `maestri portal check`):
  - name: "Score" - url: http://127.0.0.1:4173
"""

FLOORS = """Floors in "Ze":
  Ground — ~/coding/ze  ·  branch 'main'  ·  active
  "191b" — branch '191b-plugin-modules'  ·  git worktree at ~/coding/.maestri/floors/ze--191b-plugin-modules  ·  10 nodes
"""

ROUTINES = """Routines in "Ze":
  [f915d1] Weekly docs sweep  ·  Mon at 9:00 AM  ·  → Claude Code  ·  enabled  ·  next: 26 Oct 2026 at 09:00
  [1ce166] Stall check  ·  Every 10 min  ·  → Claude Code  ·  disabled
"""


def test_parse_agents_skips_you_and_portals():
    agents = pausectl.parse_agents(LIST)
    assert [a["name"] for a in agents] == ["Gauge", "Byline", "Socket"]
    assert agents[0] == {"name": "Gauge", "role": "Reviewer", "floor": "Ground", "running": True}
    assert agents[1]["role"] == "" and agents[1]["floor"] == "Ground"
    assert agents[2]["running"] is False


def test_parse_floors_excludes_ground():
    floors = pausectl.parse_floors(FLOORS)
    assert len(floors) == 1
    assert floors[0]["name"] == "191b"
    assert floors[0]["branch"] == "191b-plugin-modules"
    assert floors[0]["path"] == str(Path.home() / "coding/.maestri/floors/ze--191b-plugin-modules")


def test_parse_routines_reads_enabled_state():
    routines = pausectl.parse_routines(ROUTINES)
    assert [(r["name"], r["enabled"]) for r in routines] == [
        ("Weekly docs sweep", True),
        ("Stall check", False),
    ]


def test_resume_id_takes_the_last_one_printed():
    screen = (
        "Resume this session with:\nclaude --resume 11111111-1111-1111-1111-111111111111\n"
        "...\nclaude --resume 5509415f-1e96-4c30-8c0a-35385251c8a3 --model sonnet\n"
    )
    assert pausectl.resume_id(screen) == "5509415f-1e96-4c30-8c0a-35385251c8a3"
    assert pausectl.resume_id("no id here") == ""


def test_tier_for_model():
    assert pausectl.tier_for_model("claude-sonnet-5-5") == "sonnet"
    assert pausectl.tier_for_model("claude-opus-5-5") == "opus"
    assert pausectl.tier_for_model("claude-fable-5-1") == "fable"
    assert pausectl.tier_for_model("") == ""


def test_role_key_maps_maestri_role_back():
    assert pausectl.role_key("Reviewer", ROLES) == "ground-review"
    assert pausectl.role_key("", ROLES) == ""


def test_launch_command_resumes_the_recorded_session_on_its_tier():
    agent = {"name": "Gauge", "tier": "sonnet", "role_key": "ground-review", "session": "abc"}
    assert pausectl.launch_command(agent, ROLES) == (
        "ZE_ROLE=ground-review ZE_AGENT=Gauge " + ROLES["tiers"]["sonnet"] + " --resume abc"
    )


def test_launch_command_falls_back_to_continue_and_sonnet():
    cmd = pausectl.launch_command({"name": "Lane Two"}, ROLES)
    assert cmd == "ZE_AGENT='Lane Two' " + ROLES["tiers"]["sonnet"] + " --continue"


def test_launch_command_fable_has_its_own_model_flag():
    cmd = pausectl.launch_command({"name": "Orrery", "tier": "fable", "session": "x"}, ROLES)
    assert "claude --model claude-fable-5-1 --resume x" in cmd
