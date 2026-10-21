---
name: ze-continue
description: Continues Ze development after a pause. It restarts Docker, the Ground servers and the routines, then relaunches each floor's agents on their own sessions, one floor at a time, and sends them back to their pause handoffs. Use when the user asks to continue, resume or pick up where the team left off.
disable-model-invocation: true
---

# Continue after a pause (Maestro only, from Ground)

1. **Read before acting.** Read the newest `journal/pause/<stamp>.md`, including its Maestro summary, the matching `project_ze_pause_*` memory, and the PAUSE entries in "Ground Handoffs". Note halted floors: they stay asleep.

2. **Check the machine.**
   - Load and the process count: `ps -ax | wc -l` should be well under the per-user limit of 2666.
   - Free disk space.
   - Kill leaked docker clients: `pkill -f "stats --all --no-trunc"`.

   If forks fail, use `exec <command>` for single commands and clean up first, as described in the process-hygiene memory.

3. **Infrastructure.** Run `python3 scripts/process/pausectl.py resume --infra-only`. It starts Docker Desktop and waits for it, starts the compose services (Postgres when the pause could not read them), restarts the recorded Ground servers with their env (logs in `~/.maestri-ze/logs/`), and re-enables the routines that were on. Verify each one:
   - `docker compose exec -T postgres pg_isready -U ze`
   - the API answers on its port (`/api/v0/version`)
   - the web app answers on 5183
   - the Score portal answers on 4173

   Fix anything that fails before you wake agents.

4. **Agents, one floor at a time.**
   1. Run `python3 scripts/process/pausectl.py resume --floor Ground`, then `--floor "<Floor>"` for each floor in the summary's order. Never name a halted floor. The script retypes each agent's recorded command (`claude --resume <session>` on its recorded model, with `ZE_ROLE`), and waits while the load is above `--max-load` (default 60).
   2. After each floor, `maestri check` every agent. A Claude TUI means it came back. A bare shell or a "No conversation found" error means you relaunch it by hand: type the printed command, or use `--continue` in its directory.
   3. Brief every agent that came back with one batch:

      > RESUMED after pause <stamp>. Read your PAUSE entry in your floor's Handoffs note and your state file, run `git status`, then continue from your next step. Reply with one line: `resumed: <next step>`.

      Floor leads wake their own lanes only when they need them.

5. **Close the loop.**
   - Update the score floor states, add a "Resumed <date>" line under the roadmap's pause line, and update your state file.
   - Set `"resumed_at"` in the snapshot JSON.
   - Report to the user: a table with one row per floor showing where it is and what happens next, the agents that needed a manual relaunch, and anything still broken.
