# Quickstart: Memory Facts Hard-Cut

## Prerequisites

- Phase 133 (perception facts on the seam) implemented or at least specified with the
  call-site contract this phase assumes.
- Postgres + `make migrate` after `zm020` exists.
- Dev DB may be wiped (`pre-v1-hard-cuts`).

## Blocker check (do this first)

```bash
rg "propose_facts\\(" --glob '*.py' \
  core/engine plugins core/ops core/automation \
  -g '!**/tests/**'
```

If any **production** hit remains that is not a `write=` bound to persist inside
`ze_memory`, stop and return the miss to Phase 133. Do not add a wrapper.

## Validate types and SQL

```bash
make test-memory
```

Expect:

- `Fact(provenance="raw")` fails type/value checks in new tests.
- Retrieval fixtures no longer use `"raw"`; they use `Provenance.PROMPT_SUPPLIED` /
  `"prompt_supplied"`.
- Decay tests still select synthesized uncorroborated rows.

```bash
make test-api
```

Fact-quality tests: `by_provenance` has `prompt_supplied`, not `raw`.

## Persist path

1. Submit a perception `Contribution` with `Provenance.PROMPT_SUPPLIED` (133 helper).
2. Read the row: `provenance = 'prompt_supplied'`.
3. Confirm `MemoryStore` has no `propose_facts` (grep Protocol).

## Constitution

No dual-write. One migration. Private persist only.
