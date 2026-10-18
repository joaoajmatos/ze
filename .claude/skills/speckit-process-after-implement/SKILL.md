---
name: speckit-process-after-implement
description: Checks that a finished phase reads Implemented everywhere. Use when speckit finishes implementing and the after_implement hook fires.
---

# After implement: check phase status

Tick each finished task in `tasks.md` in the commit that finishes it. Then run:

```bash
python3 scripts/process/check_phase_status.py specs/phases/NNN-name
```

When every task is ticked, `spec.md` Status, the AGENTS.md phase row and the `specs/README.md` row must all say Implemented. The check exits 1 and names the one that does not. Fix it in the same commit; do not report the phase as done while it fails.
