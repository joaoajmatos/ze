---
name: ze-pause
description: Pauses all Ze development. Every agent writes a pause handoff, then the Maestro records a snapshot and stops the agents, floors, routines, dev servers and Docker, so the machine is free for another project. Use when the user asks to pause, stop for now, or switch to another project.
disable-model-invocation: true
---

# Pause development (Maestro only, from Ground)

The goal: nothing of Ze keeps running, and `/ze-continue` can pick up every thread exactly where it stopped. Run the steps in order. Do not skip the handoffs: an agent stopped without one loses its in-flight context.

1. **Snapshot.** `python3 scripts/process/pausectl.py snapshot` writes `journal/pause/<stamp>.json` and `.md`: floors (head, ahead of main, dirty files, last review, open tasks), agents, routines, Ground dev servers with their env, and Docker services. Keep the path.

2. **Handoffs from every running agent.** Send one batch (`maestri ask --batch`) to every agent the snapshot marks running, with a 10-minute timeout:

   > PAUSE <stamp>: the user is pausing all Ze development. Within 5 minutes, stop at a safe point. Finish or abandon the current command, and start no new gates or reviews. Commit finished work on your own paths only and leave work in progress uncommitted. Append a `### <date> PAUSE <Name> [<Floor>]` entry to your floor's Handoffs note ("Ground Handoffs" on Ground) with: done since your last entry, in flight (files, uncommitted or not), the exact next step, what you wait on (who or what), and commands to rerun. Update your state file `journal/state/$MAESTRI_TERMINAL_ID.md` the same way. Stop any dev server you started. Then reply with one line: `paused: <next step>`.

   Any agent that does not reply: `maestri check` it. If it is mid-turn after 10 minutes, press Esc (`--raw '\e'`) and ask again. If it cannot reply (bare shell, crashed), write its entry yourself from its terminal, `git status` and its tasks.md rows.

3. **The Maestro's summary.** Append `## Maestro summary` to `journal/pause/<stamp>.md` with:
   - a status table with one row per floor: where it is, what the next step is, and who acts next;
   - the order in which to resume floors;
   - halted floors that must not be woken;
   - open user decisions;
   - blockers (Docker, credits, limits).

   Then update:
   - your state file;
   - the floor notes in `journal/score/score.ze`;
   - one line in the "Ze Roadmap" note: `Paused <stamp> → journal/pause/<stamp>.md`;
   - a memory `project_ze_pause_<date>.md` that points at the pause file (do not copy the file into it).

4. **Stop everything.** `python3 scripts/process/pausectl.py stop journal/pause/<stamp>.json` does the following:
   - disables the enabled routines;
   - sends `/exit` to each running agent and records the session id and model it printed;
   - unloads every floor;
   - stops the dev servers and the leaked docker clients;
   - stops the compose services and quits Docker Desktop.

   It writes all of this back into the snapshot. Preview with `--dry-run`. It names any agent whose session id it could not read; that agent resumes with `--continue` in its own directory.

5. **Report to the user.** Give the pause file path, a one-line status per floor, and anything left running (the Maestro itself, which the user closes). Tell the user to start again with `/ze-continue` in the Maestro terminal.

Never pause by dismissing agents or deleting floors: those lose the agent's connections and notes.
