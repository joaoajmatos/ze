---
name: ze-recruit
description: Recruits an agent with the right role and model tier and confirms its brief arrived. Use when the Maestro staffs a floor or a lane.
disable-model-invocation: true
---

# Recruit an agent (Maestro only)

Write the brief to a file in your own scratchpad first. The brief must name: the state-file path (`journal/state/<terminal id>.md`), the scratchpad rule, the pre-review checklist, the commit trailer, the reviewer's name and the throwaway `ze_e2e_*` DB.

Then run exactly:

`scripts/process/recruit.sh "<Name>" <role> <tier> "<Floor>" <brief-file> --note "<Floor> Handoffs"`

- `role`: `maestro`, `architect`, `eng`, `jr`, `review`, `qa` or `docs`. `scripts/process/roles.toml` lists which tiers each role may use. The script refuses a mismatch such as an engineer on Opus.
- It lints the brief, recruits with `ZE_ROLE` set, waits for the terminal to be ready, sends the brief with a "reply ready" ping, and retries once with `recruit --replace`.
- `--connect "<Agent>"` (repeatable) wires the new agent to that agent right after the recruit. `maestri ask` reaches connected agents only, so review requests and verdicts depend on it. Pass the floor's reviewer for every lead and engineer, and the lead for every lane agent. When you recruit the reviewer after the crew, wire each one with `maestri connect "<Reviewer>" "<Agent>" --agent`.
- If it exits 1, the brief did not arrive. Read the agent's terminal with `maestri check` before trying again; do not assume the agent is working.

Preview with `--dry-run`.
