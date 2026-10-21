#!/usr/bin/env python3
"""Pause and continue the whole team: agents, floors, routines, dev servers and Docker.

Usage (Maestro only, from Ground):
  pausectl.py snapshot            write journal/pause/<stamp>.json + .md (what runs now); prints the path
  pausectl.py stop <snapshot>     exit every agent (recording its session), unload floors, disable routines,
                                  stop dev servers and Docker; updates the snapshot
  pausectl.py resume [<snapshot>] [--floor NAME ...] [--infra-only] [--max-load N]
                                  start Docker and the recorded Ground servers, re-enable routines, then
                                  relaunch the agents of the named floors (all when none named) on their
                                  recorded session, one floor at a time while the load is under --max-load
Every step skips what is already done, so re-running is safe. Add --dry-run to print instead of act.
"""

import argparse
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
import tomllib
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import handoff  # noqa: E402

ROOT = HERE.parents[1]
PAUSES = ROOT / "journal" / "pause"
FLOORS = Path.home() / "coding" / ".maestri" / "floors"
LOGS = Path.home() / ".maestri-ze" / "logs"
SERVER_RE = re.compile(
    r"vite|esbuild --service|uvicorn|uv run|http\.server|score|bun run dev"
)
KEEP_ENV = re.compile(
    r"^(DATABASE_URL\w*|ZE_\w+|PORT|CONFIG_DIR|EVAL_MODE|AUTO_\w+|LOG_\w+|PUBLIC_URL|VITE_\w+)$"
)
DEFAULT_SERVICES = ["postgres"]
RESUME_RE = re.compile(r"claude --resume ([0-9a-f-]{36})")
LIST_RE = re.compile(r'^  - name: "([^"]+)"(.*)$')
TUI_MARKERS = ("? for shortcuts", "auto mode", "bypass permissions", "shift+tab")
DRY = False


def sh(*args: str, timeout: float = 30) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 124, "", "timeout")
    except FileNotFoundError:
        return subprocess.CompletedProcess(args, 127, "", "not found")


def act(desc: str, fn, *args):
    if DRY:
        print(f"(dry run) {desc}")
        return None
    print(desc)
    return fn(*args)


# ── parsing (pure) ────────────────────────────────────────────────────────────


def parse_agents(listing: str) -> list[dict]:
    """Connected agents from `maestri list` (the You: block and portals/notes are skipped)."""
    agents, section = [], ""
    for line in listing.splitlines():
        if line and not line.startswith(" "):
            section = line
            continue
        m = LIST_RE.match(line)
        if not m or not section.startswith("Connected agents"):
            continue
        fields = dict(re.findall(r'(\w+): "([^"]*)"', m.group(2)))
        agents.append(
            {
                "name": m.group(1),
                "role": fields.get("role", ""),
                "floor": fields.get("floor", "Ground"),
                "running": fields.get("status") != "not running",
            }
        )
    return agents


def parse_floors(listing: str) -> list[dict]:
    """Floors from `maestri floor list` (Ground excluded)."""
    floors = []
    for line in listing.splitlines():
        m = re.match(r'^  "([^"]+)" — branch \'([^\']+)\'.*?at (\S+)', line)
        if m:
            path = m.group(3).replace("~", str(Path.home()), 1)
            floors.append({"name": m.group(1), "branch": m.group(2), "path": path})
    return floors


def parse_routines(listing: str) -> list[dict]:
    out = []
    for line in listing.splitlines():
        m = re.match(r"^\s*\[(\w+)\] (.+?)  ·  .*·  (enabled|disabled)", line)
        if m:
            out.append(
                {
                    "id": m.group(1),
                    "name": m.group(2),
                    "enabled": m.group(3) == "enabled",
                }
            )
    return out


def resume_id(screen: str) -> str:
    found = RESUME_RE.findall(screen)
    return found[-1] if found else ""


def tier_for_model(model: str) -> str:
    for tier in ("opus", "sonnet", "haiku", "fable"):
        if tier in model:
            return tier
    return ""


def role_key(maestri_role: str, roles: dict) -> str:
    for key, spec in roles["roles"].items():
        if spec.get("maestri_role") == maestri_role:
            return key
    return ""


def launch_command(agent: dict, roles: dict) -> str:
    """The shell command that resumes the agent's own session on its own model and role."""
    tier = agent.get("tier") or "sonnet"
    base = roles["tiers"].get(tier) or (
        "claude --model claude-fable-5-1"
        if tier == "fable"
        else roles["tiers"]["sonnet"]
    )
    env = []
    if agent.get("role_key"):
        env.append(f"ZE_ROLE={agent['role_key']}")
    env.append(f"ZE_AGENT={shlex.quote(agent['name'])}")
    session = f"--resume {agent['session']}" if agent.get("session") else "--continue"
    return " ".join(env + [base, session])


# ── facts about the machine ───────────────────────────────────────────────────


def session_model(session: str) -> str:
    if not session:
        return ""
    for path in (Path.home() / ".claude" / "projects").glob(f"*/{session}.jsonl"):
        models = re.findall(
            r'"model":"(claude-[\w.-]+)"', path.read_text(errors="ignore")
        )
        if models:
            return models[-1]
    return ""


def proc_env(pid: int) -> dict:
    out = sh("ps", "-E", "-ww", "-o", "command=", "-p", str(pid)).stdout
    env = dict(re.findall(r"(?:^|\s)([A-Z][A-Z0-9_]*)=(\S+)", out))
    return {k: v for k, v in env.items() if KEEP_ENV.match(k)}


def servers() -> list[dict]:
    """Our listening dev servers: pid, port, cwd, command, the env that matters, and whether Ground owns it."""
    out = sh(
        "lsof",
        "-nP",
        "-a",
        "-u",
        os.environ.get("USER", ""),
        "-iTCP",
        "-sTCP:LISTEN",
        "-Fpn",
    ).stdout
    ports: dict[int, set[int]] = {}
    pid = 0
    for line in out.splitlines():
        if line.startswith("p"):
            pid = int(line[1:])
        elif line.startswith("n") and pid:
            m = re.search(r":(\d+)$", line)
            if m:
                ports.setdefault(pid, set()).add(int(m.group(1)))
    found = []
    for pid, plist in sorted(ports.items()):
        command = sh("ps", "-ww", "-o", "command=", "-p", str(pid)).stdout.strip()
        if not SERVER_RE.search(command):
            continue
        cwd = sh("lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn").stdout
        cwd = next((ln[1:] for ln in cwd.splitlines() if ln.startswith("n")), "")
        found.append(
            {
                "pid": pid,
                "ports": sorted(plist),
                "cwd": cwd,
                "command": command,
                "env": proc_env(pid),
                "ground": cwd.startswith(str(ROOT)),
            }
        )
    return found


def docker_containers() -> list[str] | None:
    """Running compose services, or None when Docker does not answer (then resume starts DEFAULT_SERVICES)."""
    r = sh("docker", "compose", "ps", "--services", "--status", "running", timeout=15)
    return r.stdout.split() if r.returncode == 0 else None


def floor_facts(floor: dict) -> dict:
    path = floor["path"]
    git = lambda *a: sh("git", "-C", path, *a).stdout.strip()  # noqa: E731
    reviews = sorted(
        Path(path, ".process", "reviews").glob("*.json"), key=os.path.getmtime
    )
    last = json.loads(reviews[-1].read_text()) if reviews else {}
    tasks = list(Path(path, "specs", "phases").glob("*/tasks.md"))
    open_tasks = sum(
        t.read_text().count("\n- [ ]")
        for t in tasks
        if floor["branch"].split("-")[0] in t.parent.name
    )
    return {
        **floor,
        "head": git("rev-parse", "--short", "HEAD"),
        "ahead_of_main": git("rev-list", "--count", "main..HEAD"),
        "dirty": len(git("status", "--porcelain").splitlines()),
        "last_review": {
            "range": f"{str(last.get('from', ''))[:8]}..{str(last.get('to', ''))[:8]}",
            "reviewer": last.get("reviewer"),
            "verdict": last.get("verdict") or last.get("state"),
            "at": last.get("at"),
        }
        if last
        else None,
        "open_tasks": open_tasks,
    }


def load_avg() -> float:
    return float(sh("sysctl", "-n", "vm.loadavg").stdout.strip("{} \n").split()[0] or 0)


# ── commands ──────────────────────────────────────────────────────────────────


def snapshot() -> Path:
    PAUSES.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    data = {
        "paused_at": datetime.now().isoformat(timespec="seconds"),
        "main": sh(
            "git", "-C", str(ROOT), "rev-parse", "--short", "main"
        ).stdout.strip(),
        "unpushed": sh(
            "git", "-C", str(ROOT), "rev-list", "--count", "remote/main..main"
        ).stdout.strip(),
        "agents": parse_agents(handoff.maestri("list").stdout),
        "floors": [
            floor_facts(f)
            for f in parse_floors(handoff.maestri("floor", "list").stdout)
        ],
        "routines": parse_routines(handoff.maestri("routine", "list").stdout),
        "servers": servers(),
        "docker": docker_containers(),
        "stopped": False,
    }
    path = PAUSES / f"{stamp}.json"
    path.write_text(json.dumps(data, indent=2) + "\n")
    write_markdown(path, data)
    print(path)
    return path


def write_markdown(path: Path, data: dict) -> None:
    lines = [
        f"# Pause {data['paused_at']}",
        "",
        f"main {data['main']} · unpushed {data['unpushed']}",
        "",
        "## Floors",
        "",
    ]
    lines += [
        "| Floor | Branch | Head | Ahead | Dirty | Last review | Open tasks |",
        "|---|---|---|---|---|---|---|",
    ]
    for f in data["floors"]:
        r = f["last_review"] or {}
        lines.append(
            f"| {f['name']} | {f['branch']} | {f['head']} | {f['ahead_of_main']} | {f['dirty']} | "
            f"{r.get('verdict', '-')} {r.get('range', '')} | {f['open_tasks']} |"
        )
    lines += [
        "",
        "## Agents",
        "",
        "| Agent | Floor | Role | Running | Tier | Session |",
        "|---|---|---|---|---|---|",
    ]
    for a in data["agents"]:
        lines.append(
            f"| {a['name']} | {a['floor']} | {a['role']} | {a['running']} | {a.get('tier', '')} | {a.get('session', '')} |"
        )
    lines += ["", "## Ground servers (restarted on resume)", ""]
    lines += [
        f"- :{','.join(map(str, s['ports']))} `{s['command'][:120]}` in {s['cwd']}"
        for s in data["servers"]
        if s["ground"]
    ]
    lines += ["", "## Routines enabled at pause", ""]
    lines += [f"- {r['name']}" for r in data["routines"] if r["enabled"]]
    lines += [
        "",
        "Docker services running: "
        + (
            "unknown (Docker did not answer)"
            if data["docker"] is None
            else ", ".join(data["docker"]) or "none"
        ),
        "",
    ]
    path.with_suffix(".md").write_text("\n".join(lines))


def exit_agent(agent: dict) -> None:
    """Quit the agent's Claude so the terminal prints its session id; record session and model."""
    screen = handoff.maestri("check", agent["name"]).stdout
    if not any(m in screen for m in TUI_MARKERS):
        agent["session"] = resume_id(screen)
    else:
        handoff.maestri("ask", agent["name"], "--raw", "/exit\r")
        for _ in range(15):
            time.sleep(2)
            screen = handoff.maestri("check", agent["name"]).stdout
            if resume_id(screen):
                break
        agent["session"] = resume_id(screen)
    agent["model"] = session_model(agent.get("session", ""))
    agent["tier"] = tier_for_model(agent["model"])


def stop(path: Path) -> None:
    data = json.loads(path.read_text())
    roles = tomllib.loads((HERE / "roles.toml").read_text())
    for r in data["routines"]:
        if r["enabled"]:
            act(
                f"disable routine {r['name']}",
                handoff.maestri,
                "routine",
                "disable",
                r["name"],
            )
    for a in data["agents"]:
        a["role_key"] = role_key(a["role"], roles)
        if a["running"] and not a.get("session"):
            act(f"exit {a['name']} ({a['floor']})", exit_agent, a)
    for f in data["floors"]:
        act(f"unload floor {f['name']}", handoff.maestri, "floor", "unload", f["name"])
    for s in data["servers"]:
        act(f"stop :{s['ports']} pid {s['pid']}", os.kill, s["pid"], signal.SIGTERM)
    act("kill leaked docker clients", sh, "pkill", "-f", "stats --all --no-trunc")
    if data["docker"]:
        act(
            f"docker compose stop {' '.join(data['docker'])}",
            sh,
            "docker",
            "compose",
            "stop",
            *data["docker"],
        )
    act("quit Docker Desktop", sh, "osascript", "-e", 'quit app "Docker"')
    data["stopped"] = not DRY
    if not DRY:
        path.write_text(json.dumps(data, indent=2) + "\n")
        write_markdown(path, data)
    missing = [
        a["name"] for a in data["agents"] if a["running"] and not a.get("session")
    ]
    if missing:
        print(
            "no session id recorded for: "
            + ", ".join(missing)
            + " (resume falls back to --continue)"
        )


def wait_docker(seconds: int = 240) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if sh("docker", "info", timeout=15).returncode == 0:
            return True
        time.sleep(5)
    return False


def start_server(s: dict) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    log = (LOGS / f"server-{s['ports'][0]}.log").open("a")
    subprocess.Popen(
        s["command"],
        shell=True,
        cwd=s["cwd"],
        env={**os.environ, **s["env"]},
        stdout=log,
        stderr=log,
        start_new_session=True,
    )


def port_open(port: int) -> bool:
    return sh("lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN").returncode == 0


def relaunch(agent: dict, roles: dict) -> None:
    command = launch_command(agent, roles)
    handoff.maestri("ask", agent["name"], "--raw", "\x03")
    time.sleep(1)
    screen = handoff.maestri("check", agent["name"]).stdout
    if any(m in screen for m in TUI_MARKERS):
        handoff.maestri("ask", agent["name"], "--raw", "/exit\r")
        time.sleep(4)
    handoff.maestri("ask", agent["name"], "--raw", command + "\r")


def resume(path: Path, floors: list[str], infra_only: bool, max_load: float) -> None:
    data = json.loads(path.read_text())
    roles = tomllib.loads((HERE / "roles.toml").read_text())
    services = DEFAULT_SERVICES if data["docker"] is None else data["docker"]
    if services or any(s["ground"] for s in data["servers"]):
        act("start Docker Desktop", sh, "open", "-a", "Docker")
        if not DRY and not wait_docker():
            sys.exit(
                "Docker did not answer within 4 minutes; fix Docker, then run resume again"
            )
        if services:
            act(
                f"docker compose up -d {' '.join(services)}",
                sh,
                "docker",
                "compose",
                "up",
                "-d",
                *services,
                timeout=180,
            )
    for s in data["servers"]:
        if s["ground"] and not port_open(s["ports"][0]):
            act(f"start :{s['ports'][0]} {s['command'][:80]}", start_server, s)
    for r in data["routines"]:
        if r["enabled"]:
            act(
                f"enable routine {r['name']}",
                handoff.maestri,
                "routine",
                "enable",
                r["name"],
            )
    if infra_only:
        return
    order = ["Ground"] + [f["name"] for f in data["floors"]]
    wanted = [f for f in order if not floors or f in floors or f == "Ground"]
    for floor in wanted:
        agents = [
            a
            for a in data["agents"]
            if a["floor"] == floor and a["running"] and not a.get("resumed")
        ]
        if not agents:
            continue
        while not DRY and load_avg() > max_load:
            print(f"load {load_avg():.0f} > {max_load:.0f}: waiting before {floor}")
            time.sleep(30)
        for a in agents:
            act(
                f"relaunch {a['name']} ({floor}): {launch_command(a, roles)}",
                relaunch,
                a,
                roles,
            )
            a["resumed"] = not DRY
        if not DRY:
            path.write_text(json.dumps(data, indent=2) + "\n")
            time.sleep(20)


def latest() -> Path:
    found = sorted(PAUSES.glob("*.json"))
    if not found:
        sys.exit("no snapshot in journal/pause/")
    return found[-1]


def main(argv: list[str]) -> int:
    global DRY
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["snapshot", "stop", "resume"])
    ap.add_argument("snapshot", nargs="?")
    ap.add_argument("--floor", action="append", default=[])
    ap.add_argument("--infra-only", action="store_true")
    ap.add_argument("--max-load", type=float, default=60)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    DRY = args.dry_run
    if args.command == "snapshot":
        snapshot()
        return 0
    path = Path(args.snapshot) if args.snapshot else latest()
    if args.command == "stop":
        stop(path)
    else:
        resume(path, args.floor, args.infra_only, args.max_load)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
