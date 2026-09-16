# Quickstart: Per-Delegate Gate

1. Fail-first: worker gate ≠ parent copy; lookup then write isolation.
2. Inject evaluate callback from `execute_tool`; implement in `run_delegate`.
3. Optional `intent` on the tool schema.
4. AWAIT_CONFIRMATION → 113 `request_id` pause/resume.
5. Lock graph parallel strictest-wins tests.
6. Do not delete `plan_sequential` or change companion `description`.
