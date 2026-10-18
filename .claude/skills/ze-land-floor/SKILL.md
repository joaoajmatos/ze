---
name: ze-land-floor
description: Lands a reviewed floor into main behind code checks and pushes it. Use when the Maestro is asked to land a floor, or a floor in review has a reviewer APPROVE and a QA pass.
disable-model-invocation: true
---

# Land a floor (Maestro only)

Run these steps exactly, in order. Stop at the first failure and report it. Do not work around a failed check.

1. Preflight, from the floor's checkout:
   `make process-land-preflight FLOOR=<floor path>`
   It checks history and merge conflicts, untracked files in the floor and Ground, phase status sync, new files under `specs/arch/`, the gate receipt for the floor HEAD, and the APPROVE review chain. Fix what it names; never edit receipts or review records by hand.
2. Land: `maestri floor land "<floor>" --into main`.
3. In Ground, run the full gates and record the receipt with this one command:
   `make process-gates PROFILE=land`
   It must exit 0. Run no raw `make test-py`, `test-web` or other gate first: the push accepts only this receipt, and each full gate would run twice.
4. Post-land, in Ground:
   `scripts/process/land_post.sh`
   It refreshes the graph and pushes main. It skips any step already done, so re-running is safe. The push hook refuses without a green receipt for HEAD.
5. By hand, because they need judgment: the score line and roadmap line, then dismiss the floor's agents, delete the floor, remove lane worktrees and archive state files.

Preview without side effects: `python3 scripts/process/land_preflight.py --dry-run` and `scripts/process/land_post.sh --dry-run`.

Never force-push, and never push main from any role but the Maestro.
