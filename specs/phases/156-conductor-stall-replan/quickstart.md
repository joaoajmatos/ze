# Quickstart: Conductor Stall / Replan

1. Implement 155 first (mixed turns reach companion).
2. Add counters on context/state; persist across confirmation resume.
3. Enforce detector + caps in `run_delegate`.
4. Write `stalled` / `replanned` / `ask_user` on `conductor_ledger`.
5. Mirror policy in companion instructions.
6. Tests: retry once, then block; confirmation is not stall.
7. Do not create workflows/goals. Do not implement 157.
