# Quickstart: Programmatic Tool Use (197)

## Offline gates

```bash
make test-agents             # contract, stub builder, script step dispatch, loop branch, proposed writes, flatten, cap hook
make test-core               # trace fields and access "script", retry eligibility, spend charge, execute_tool passes the runner
make test-workspace          # runner (fake WS sidecar), learning (ledger + candidate), client, bootstrap
make test-memory             # ActionContext.script_key + list_by_script_key, procedures (source kind, guidance, validate)
make test-workspace-sidecar  # relay protocol, slot, caps, pipe framing (no root needed)
make test-components test-priority   # produces_ui on render and show tools
make test-eval               # max_llm_calls assertion, tool_scripts.yaml loads
make test-py && make test-web && make typecheck-web
make test-pg                 # three runs of one script key leave three ledger rows (real idempotency path)
```

## Sandbox smoke test (Docker, local)

1. `docker-compose.yml` gives the workspace service `cap_add: [NET_ADMIN]`; `make workspace-up`.
2. `curl -s -H "Authorization: Bearer $WORKSPACE_API_TOKEN" localhost:8081/stat` shows `scripts_isolated: true`.
3. Run `python sidecar/workspace/tests/smoke_scripts.py` (marked `docker`). It opens `WS /scripts` and checks that:
   - `urllib.request.urlopen("https://example.com")` fails fast (connection refused by the reject rule);
   - `open("/workspace/x")` and `os.listdir("/workspace")` fail with a permission error;
   - allocating 512 MiB ends the script `resource_limit`; a fork loop ends `resource_limit`; writing a 40 MiB file ends `resource_limit`;
   - a `setsid` child is gone after the script ends;
   - `print("x" * 10_000_000)` does not hang (stdout discarded);
   - a script calling `z.echo(x=1)` against a fake dispatcher gets `1` back;
   - a handshake without the token, or with no token configured, is refused with 1008.

Without `NET_ADMIN` (for example a container started without it), `scripts_isolated` is false and the script tool reports `sandbox_unavailable`.

## Manual (local dev)

1. `make dev-full`; in Ask: "What did I spend by merchant this month? Top five."
2. Expect the finance agent to answer in one reply. The trace shows one "Script" row that expands to its source and nested calls, and the readouts show two model calls.

## Live eval (only with the user's OK; costs credits)

```bash
python eval/run.py --tag tool_scripts
```
