# Quickstart: Programmatic Tool Use (197)

## Offline gates

```bash
make test-agents       # contract, stub builder, script step dispatch, loop branch, proposed writes, flatten
make test-core         # trace fields, spend charge, execute_tool passes the runner
make test-workspace    # runner (fake WS sidecar), learning (ledger + candidate), client URL
make test-memory       # ProcedureSourceKind, discovery source_kind
make test-sidecar      # relay protocol, slot, limits, pipe framing (no root needed)
make test-eval         # max_llm_calls assertion, tool_scripts.yaml loads
make test-py && make test-web && make typecheck-web
```

## Sandbox smoke test (Docker, local)

1. `make workspace-up`.
2. `curl -s -H "Authorization: Bearer $WORKSPACE_API_TOKEN" localhost:8081/stat` shows `scripts_isolated: true`.
3. Run `python sidecar/workspace/tests/smoke_scripts.py` (marked `docker`): it opens `WS /scripts` and runs three scripts, checking that
   - `urllib.request.urlopen("https://example.com")` fails with a network error;
   - `open("/workspace/x")` fails with a permission error;
   - a script that calls `z.echo(x=1)` against a fake dispatcher gets `1` back.

## Manual (local dev)

1. `make dev-full`; in Ask: "Which of my active goals involve people I haven't contacted in a month?"
2. Expect companion to answer in one reply. The trace shows one "Script" row that expands to its source and nested calls, and the readouts show two model calls.

## Live eval (only with the user's OK; costs credits)

```bash
python eval/run.py --tag tool_scripts
```
