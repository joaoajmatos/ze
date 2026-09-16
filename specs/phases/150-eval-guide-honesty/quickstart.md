# Quickstart: Eval + Guide Honesty

1. Delete `memory_proposals_count` from `EvalChatResponse` and the eval route.
2. Update MCP docstrings and `docs/eval.md`.
3. Regenerate `@ze/client` types.
4. Tests assert the field is absent (OpenAPI + model).
5. Sync `AGENTS.md` and `CLAUDE.md` to `specs/README.md` for 140–150.
6. Do not add a 151 directory.
