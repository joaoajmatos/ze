---
name: speckit-process-after-tasks
description: Runs the Ze lane-plan and speckit-flow checks on the feature that just got its tasks. Use when speckit finishes generating tasks.md and the after_tasks hook fires.
---

# After tasks: check the crew plan

Run both checks on the current feature directory (`specs/phases/NNN-name`):

```bash
python3 scripts/process/check_lane_plan.py specs/phases/NNN-name
python3 scripts/process/check_speckit_flow.py specs/phases/NNN-name
```

Each exits 1 and names what is wrong: a missing Lane Plan, lanes that share a file, a task without `[L:x]`, a missing Clarifications section, or (for a complex phase) a missing checklist or analyze result.

Fix the artifacts and rerun until both exit 0. Do not report the tasks as done while either fails.
