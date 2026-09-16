# Quickstart: Memory Prompt Constitution (Phase 141)

## Validate

```bash
make test-agents
make test-memory
make test-personal
make test-core
make lint
```

## Checks

1. Prompt fixture: reviewed fact appears; 20 irrelevant facts do not all appear.
2. Constitution + job substrings have lower index than “Known facts” / formatted memory.
3. Companion instructions include silent-use; no unsolicited recitation.
4. `TurnSurfacing` tests still pass unchanged for open items.
5. Calendar/mail agent instruction files not in this phase’s diff except inherited formatter tests.
