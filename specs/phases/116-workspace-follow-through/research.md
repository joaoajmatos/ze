# Phase 0 Research: Workspace Follow-Through

No `NEEDS CLARIFICATION` markers remained in Technical Context — Phase 115 already
fixed the storage/testing/platform shape this spec extends. Research below resolves
the open design questions the spec's Assumptions and FR-017 leave to plan time, each
grounded in what the codebase already does, per the constitution's "no new pattern
where an existing one fits."

## D1: How does a "follow-up turn" actually get started?

**Decision**: Reuse `container.invoke_raw_turn(thread_id, RawInput(text=...))`
(`core/ze-core/ze_core/conversation/turn.py`, wrapped by
`apps/ze-api/ze_api/container.py:ZeContainer.invoke_raw_turn`) — the exact function
the WebSocket turn handler (`apps/ze-api/ze_api/api/websocket/turns.py`) and the eval
route already call. The watcher constructs a synthetic prompt (e.g. "The workspace
run you started finished: <status>.") and passes it as `raw.text`; `invoke_raw_turn`
already streams trace events to the interface, appends to the graph's checkpointed
history via `write_memory`, and returns a `TurnResult` the same way a user-initiated
turn does.

**Rationale**: FR-003 explicitly forbids inventing a new async-conversation model.
`invoke_raw_turn` is transport-agnostic already (it takes a `thread_id` and `RawInput`,
not a WebSocket connection) — it was designed for exactly "start a turn without a live
request in flight" (the eval route already calls it outside of a WS context).

**Alternatives considered**: A dedicated "system message" injection that bypasses the
graph (cheaper, but produces a message with no routing/memory/trace — user could not
ask a follow-up about it, violating "Ze uses the run's result to continue"). A new
`ZePlugin` signal source (over-engineered for a single core-owned flow; signal sources
compose into `pre_route_node`, not turn-starting).

## D2: How does the watcher know a detached run is terminal?

**Decision**: The same coroutine that would have awaited the sidecar's `/run` call
inline keeps running as an `asyncio.create_task` after the short wait elapses, owned
by `RunWatcher` in `ze_workspace/followthrough.py`. No polling loop is needed while
the process is alive — the task already blocks on the HTTP call to the sidecar and
resumes the instant it returns, then persists the terminal `WorkspaceRunStatus` via
the existing `WorkspaceStore` write Phase 115 already has for in-turn completion.

**Rationale**: Matches CLAUDE.md's async convention directly ("Fire-and-forget tasks
use `asyncio.create_task()`") and avoids a second execution path for "the process
finished" — same code, just not awaited by the turn anymore.

**Alternatives considered**: A sidecar-pushed webhook on completion (adds a new
inbound HTTP surface and reachability requirement onto the sidecar calling back into
`ze-api`, which Phase 115's contract does not have and this spec should not introduce
just for detach). A polling job on a schedule (`ze-proactive` job) — unnecessary
latency (SC-003's "zero silent finishes" is easier with a task that is already
waiting on the exact I/O than with a periodic sweep) and duplicates Phase 115's
existing await-the-subprocess call.

**Startup gap this leaves**: if `ze-api` restarts while a run is detached, the
in-memory task is gone. Resolved as reconciliation (D5).

## D3: How is the "one turn at a time per conversation" ordering (FR-008) enforced?

**Decision**: A new `ThreadTurnLock` (`ze_workspace/turn_lock.py`) — an
`asyncio.Lock` per `thread_id`, held for the duration of any `invoke_raw_turn` /
`resume_turn` call on that thread, acquired by `apps/ze-api` around the WebSocket
turn handler, the eval route, and the `RunWatcher`'s follow-up call alike. The
watcher's follow-up simply awaits the lock before calling `TurnStarter.invoke`; if a
user is mid-reply on that thread, the follow-up waits its turn instead of racing it.

**Rationale**: No such lock exists today — `invoke_raw_turn` has no thread-level
mutual exclusion (checked directly: neither `ze_core/conversation/turn.py` nor
`ZeContainer` track in-flight turns by thread; the older `Container.invoke`'s
`_abort_tokens` dict tracks abort signaling, not mutual exclusion, and
`invoke_raw_turn` doesn't touch it). A lock is the minimal primitive that satisfies
"waits, does not interrupt" without adding a queue (spec explicitly rules out a
backlog of detached work, but says nothing against a single wait for the *next*
follow-up).

**Alternatives considered**: Checking `graph.aget_state(config).next` / LangGraph
checkpoint status as a proxy for "in progress" (racy — a turn between checkpoint
writes doesn't reliably show as busy, and Phase 115's own confirmation flow already
shows checkpoint state is not a trustworthy single-process-safe lock). A DB advisory
lock (unnecessary — `ze-api` is a single process per the deployment model in
CLAUDE.md's stack table; no multi-instance requirement exists to justify cross-process
locking).

## D4: How does the "push only if disconnected" rule attach?

**Decision**: Reuse `NativeAppInterface`'s existing connected check
(`apps/ze-api/ze_api/interface/native.py`, `self._conn.connected` gating both
`send`/`push` today) via a `PushSender` Protocol the watcher calls unconditionally —
`PushSender.send_completion(run)` internally decides connected-vs-push exactly the
way `ProactiveNotifier.notify`/`push` already do for every other proactive event
(stuck goals, accountability, reminders). The watcher does not itself branch on
connectivity; it always calls both `TurnStarter.invoke` (which delivers over the
live WebSocket when connected) and `PushSender.send_completion` (which is a no-op
push when connected, matching the doc comment already in `native.py`: "Only push via
ntfy when the WebSocket is not connected").

**Rationale**: FR-006/FR-007 are already how every other proactive channel in Ze
behaves — no new notification product per the spec's Assumptions.

**Alternatives considered**: Watcher explicitly checking `ConnectionManager` state
itself — rejected, it would duplicate a check `NativeAppInterface` already owns and
couple `ze-workspace` to `ze-api`'s WebSocket internals instead of the small Protocol
boundary the Constitution Check requires.

## D5: Startup reconciliation for in-progress runs

**Decision**: On `ze-api` boot (`compose.py`, alongside the existing proactive job
registration fan-out), `WorkspaceStore` is queried for any `workspace_runs` row with
`ended_at IS NULL`. For each, `RunWatcher.reattach(run)` is called, which re-issues
the await against the sidecar's run-status shape (Phase 115's `/stat`/run lookup) and
resumes exactly the D2 task as if detach had just happened. This mirrors Phase 13's
reminder "startup replay" precedent directly (same problem: an in-memory background
watcher must survive a process restart).

**Rationale**: Without this, a restart during a detached run silently strands it —
the run never reaches follow-through and User Story 2's "does not have to poll"
guarantee breaks exactly when it matters most (long runs are the ones most likely to
span a deploy).

**Alternatives considered**: Accept the gap (rejected — SC-003 says "zero silent
finishes," an unconditional claim, and Ze already treats this exact restart risk as
worth solving for reminders).

## D6: FR-017 short-wait / time-budget numbers

**Decision**: Short wait defaults to 25 seconds (configuration, `config/config.yaml`
`workspace:` block, same file Phase 115 already added a block to). Phase 115's
existing 120s run budget is unchanged and is the terminal `timed_out` bound
after detach.

**Rationale**: Spec's Assumptions say "tens of seconds, not minutes" for the short
wait and reaffirm the existing minutes-scale budget; 25s leaves ordinary quick
commands (file listing, small scripts) finishing in-turn while keeping the perceived
latency well under typical chat-turn patience, and leaves comfortable room before the
120s budget so "still running" replies are not a coin flip against real quick
commands.

**Alternatives considered**: A fixed fraction of the budget computed at runtime
(rejected — adds indirection for no behavioral gain versus a plain constant; FR-017
only requires the two numbers to be sensibly related, not derived from each other).
