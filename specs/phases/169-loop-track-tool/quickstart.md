# Quickstart: Loop Track Tool

```bash
make test-worldstate     # tracker, tool, store edge, agent catalog
make test-agents         # nested_tools predicates + enforcer, reversibility declaration
make test-core           # write_memory gate skip
make test                # ze-api: container DI, config
make test-eval           # verifier unchanged; scenario schema
make lint

make dev-eval            # then, in another shell:
make eval                # routing + verify for loops_track_then_list_en/pt (live, uses credits)
```

Manual: in the web chat say "I haven't decided about the Porto move, keep it on my radar". Check `GET /api/v0/loops` shows one `active` loop at 0.9, and the trace shows a `track_loop` call and no loop judgment rows. Say it again: still one loop.
