# Quickstart: Fat Delegate ACI

1. Fail-first: rewrite `test_delegate.py` for `objective`, caller `companion`, depth 1, refuse non-companion.
2. Update `DELEGATE_TOOL_SCHEMA` and `run_delegate` (assemble brief; pass caller name from `agentic_loop`).
3. Remove `delegate_to_agent` from research; fix calendar instruction.
4. Companion instructions: `objective` (+ optional fat fields). Do not edit `description`.
5. Grep `task`/`context` on delegate call sites; update 146 tests that still pass `task`.
6. Confirm graph tests for `plan_sequential` still pass without edits (or only test lock).
7. Do not implement 152–154 in this tree.
