# Quickstart: One Commitment Intake

```bash
make test-memory test-worldstate test-core test   # logic and wiring, mocked client
make migrate && make test-pg                       # zw004
make codegen && make test-web typecheck-web        # chips
make calibrate-commitment-intake -- --check-sets   # offline shape check
# live (needs the user's OK): make calibrate-commitment-intake ; then --set holdout --bars ...
```
Manual: in chat say "Remind me at 5pm to call Ana" with the surface enabled; expect one reminder, no loop, a `commitment` row in the trace.
