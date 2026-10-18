# Agent process kit

The process kit turns the team's working rules into code. Scripts check the rules. Hooks stop the worst mistakes. Skills tell an agent which script to run.

A rule that must hold every time lives in a script or a hook. Prose only advises.

## Where the pieces live

| Piece | Path | Purpose |
|---|---|---|
| Hooks | `scripts/process/hooks/` | Block a tool call before it runs (`guard_bash.py`, `guard_edit.py`) or stop a turn (`stop_gate.py`) |
| Checks | `scripts/process/` | One script per rule. Make targets, hooks, git hooks and CI all call the same script |
| Skills | `.claude/skills/ze-*` | Short wrappers that name the script to run |
| Tests | `scripts/tests/` | Run in `make test-py` through `make test-scripts` |
| Receipts | `.process/` (gitignored) | Gate results and review records for one checkout |

## When the hooks act

Every hook does nothing unless the environment variable `MAESTRI_TERMINAL_ID` is set. Your own shell is never affected.

`ZE_ROLE` scopes the role rules. The values are `maestro`, `architect`, `eng`, `jr`, `review`, `qa` and `docs`. `recruit.sh` sets it. When it is unset, the role rules do not apply.

The hooks are registered in `.claude/settings.json`. OpenCode and Cursor agents do not run Claude Code hooks. For them, `make process-install-hooks` installs the git hooks, which carry the rules that concern repository state.

### What `guard_bash.py` blocks

- `git add -A`, `git add .`, `git add -u` and `git stash`. Stage explicit paths.
- Force pushes.
- A push to `main` from any role but the Maestro. The Maestro also needs a green receipt for HEAD.
- `maestri floor land` and `floor delete` from any role but the Maestro.
- `maestri floor status --state review` from `eng` and `jr`. Use `make process-ready FLOOR=<name>`.
- `make format`, `make migrate`, `make db-reset` and any URL that points at the shared database `ze`. Use a throwaway `ze_e2e_*` database.
- `make calibrate-*` without `--check-sets` or `--recall`. A live calibration spends credits.
- A gate such as `make test-py` piped to `tail`, `head`, `grep` or `tee`. The pipe hides the exit code.

It asks the user first for `maestri role edit`, `write`, `delete` and `assign`. A role edit restarts every running agent with that role.

### What `guard_edit.py` blocks

- `AskUserQuestion` from any role but the Maestro. Batch questions to the Maestro.
- Edits by `review` outside a scratchpad directory. Reviewers are read-only.
- Hand edits to `.process/receipts/` and `.process/reviews/`.
- New files under `specs/arch/` from any role but `architect` and `maestro`.
- Writes outside the lane's globs, when `.process/lane.json` exists. The file has the form `{"lane": "a", "owns": ["apps/ze-web/src/pages/a/*"]}`. The lead writes it into a lane worktree.

### What `stop_gate.py` blocks

- A `review` agent that ends a turn while a review request has no verdict record.
- Any agent role that ends a turn while its state file is older than its last commit.

Each reason blocks a turn once. The hook respects `stop_hook_active`.

## Commands

| Command | What it does |
|---|---|
| `make process-ready` | Picks the gates the diff needs, runs them, and writes `.process/receipts/<sha>.json` |
| `make process-ready PORTAL_SHOT=<png>` | Same, and records the portal screenshot for a web change |
| `make process-ready FLOOR=<name>` | Same, and sets the floor to `review` when everything passes |
| `make process-review-request RANGE=a..b REVIEWER=<name>` | Records the request, asks the reviewer, and alerts when the reviewer shows no activity |
| `make process-review-verdict RANGE=a..b VERDICT=APPROVE\|CHANGES FINDINGS=<file>` | Records the verdict and delivers it |
| `make process-land-preflight FLOOR=<path>` | Refuses a floor that is not ready to land |
| `make process-gates PROFILE=land` | Runs every gate in Ground and writes the receipt that the push needs |
| `make process-install-hooks` | Installs the git hooks |
| `scripts/process/recruit.sh` | Recruits an agent with the right role and tier, and confirms the brief arrived |
| `scripts/process/land_post.sh` | After a land: refreshes the graph and pushes `main`. Safe to run again |
| `scripts/process/floor_check.sh` | After `floor create`: the floor must fork from the tip of `main` with a clean tree |
| `scripts/process/web_portal.sh <port>` | Serves ze-web from this checkout for a Maestri portal. `--check <port>` exits nonzero unless the page answers 200 |
| `scripts/process/skill_eval.py` | `--check` and `--dry-run` are free. `--run <skill> --yes-spend-usage` spends Claude usage |

## Gate receipts

`process-ready` reads the diff against the merge base with `main`:

- Python files select `lint` and the `test-*` target of each touched package. The script reads the package map from the Makefile.
- Web files select `typecheck-web`, `lint-web` and `test-web`.
- Each gate's exit code goes into the receipt. The script never reads the code from a pipe.

It also runs `check_query_errors.py` on changed `entities/*/api/use*Query.ts` files. Each must throw on an API error and have a test that asserts `isError`.

These checks only warn: old route literals, public docs not touched by a behavior change, and a web change without `PORTAL_SHOT`. Add `Docs: none (reason)` to a commit message to silence the docs warning.

A claim about gates or reviews must cite a file under `.process/`.

## Verify web changes in your own portal

Run `scripts/process/web_portal.sh <port>`, then the `maestri portal create` command it prints. The `ze-web-verify` skill has the full steps. The backend is the shared test API on port 8010.

## Landing a floor

The Maestro uses the `ze-land-floor` skill. `land_preflight.py` fails when:

1. The floor shares no history with `main`, or merging `main` into it conflicts.
2. The floor or Ground has untracked files that `.git/info/exclude` does not cover.
3. A fully ticked phase does not read Implemented in its `spec.md`, the AGENTS.md table and `specs/README.md` (`check_phase_status.py`).
4. The diff adds a file under `specs/arch/`.
5. No green receipt exists for the floor HEAD, or the receipt lacks a gate the diff needs.
6. The APPROVE review records do not form a chain from the merge base to HEAD.

Tick a task in `tasks.md` in the same commit that finishes it.

## Reviews as files

A request starts where the last request or verdict ended, so each review covers only new commits. The first range starts at the merge base with `main`. A `CHANGES` verdict needs a findings file. The `ze-request-review` skill covers both sides.

## Recruiting

`scripts/process/roles.toml` lists which model tiers each role may use. Engineers never run on Opus. Reviewers never run on Haiku. `recruit.sh` lints the brief for the state-file path, the scratchpad rule, the pre-review checklist, the commit trailer, the reviewer name and the throwaway database. It waits for the terminal, sends the brief with a "reply ready" ping, and retries once with `recruit --replace`. When the brief still sits in the input box with no reply, the script presses Enter (`maestri ask NAME --raw "\r"`) and waits up to 120 seconds for a reply.

## Speckit checks

The `after_tasks` hook runs `check_lane_plan.py` and `check_speckit_flow.py`. The `after_implement` hook runs `check_phase_status.py`.

- `check_lane_plan.py` needs a `lead` lane, a model and reviewer for each lane, no file owned by two lanes, and an `[L:x]` tag on every task.
- `check_speckit_flow.py` reads artifacts: a Clarifications section in `spec.md`, a Lane Plan in `plan.md` and a lane tag on each task. A phase marked `**Complexity**: complex` also needs `checklists/*.md` and an analyze result (`analysis.md`, or an `## Analysis` section).

## Skill checks

`scripts/tests/test_skills_lint.py` checks every `.claude/skills/ze-*` skill: name, a third-person description with a "Use when" clause, a body under 500 lines, existing script and make-target references, and `disable-model-invocation: true` on skills with side effects.

`skill_eval.py` holds trigger queries and behavior scenarios in `scripts/process/skill_evals/`. Run it only when a skill changes and the user agrees to the usage.

## Limits

The guards use pattern matching. They catch mistakes, not an agent that tries to get around them. Receipts and the land preflight are the real gate.
