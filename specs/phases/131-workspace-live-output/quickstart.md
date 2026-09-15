# Quickstart: Validating Workspace Live Output

## Prerequisites

- `make db-up && make migrate` (no new migration in this phase, but the workspace
  sidecar and `workspace_runs` table from Phase 129/115 must exist).
- `make dev-full` (backend on :8000, ze-web on :5173) with the workspace sidecar
  reachable, or `make dev-eval`-equivalent local setup with a workspace mode other
  than Off.

## Scenario A: Live output in chat (User Story 1 / SC-001, SC-003)

1. From the web chat, ask Ze to run a workspace command that prints several lines
   with delays (e.g. a script that echoes a line every second for ~15s) long enough
   to outlive the short wait-then-detach window (Phase 116).
2. Confirm the turn ends with the still-running chip
   (`data-testid="workspace-still-running-chip"`).
3. Stay on the conversation. Confirm new printed lines appear under the chip before
   the command exits (SC-001: at least one line visible ≥5s before exit).
4. Let the command finish. Confirm exactly one follow-up message arrives on that
   thread (SC-003) and the chip stops indicating in-progress.
5. Repeat with the browser tab closed and reopened mid-run: confirm already-produced
   lines replay immediately, then new lines continue (FR-002) — with no duplicated
   prefix.

## Scenario B: Live output on the workspace page (User Story 2 / SC-002)

1. Start the same kind of long-printing detached command.
2. Open `/workspace` while it is still running. Confirm the in-progress run in
   `RunningRunBanner` (`data-testid="running-run-banner"`) shows the same
   already-produced output as the chat conversation, and that a new line appears in
   both places without disagreement (SC-002).
3. Click "Stop" (`data-testid="cancel-run-button"`). Confirm the preview stops
   growing (FR-009) and the eventual follow-up reports the run was stopped.

## Scenario C: Redaction (SC-004)

1. Run a workspace command that prints a line containing a denylisted key pattern,
   e.g. `echo "OPENROUTER_API_KEY=sk-or-fake123"`.
2. Confirm the live line shown in chat and on `/workspace` reads `[redacted]` in
   place of the value — not the raw secret — in both the streaming view and the
   eventual terminal preview.

## Scenario D: Stream unavailable (FR-010)

1. Start a detached command, then make the sidecar/watch endpoint temporarily
   unreachable (e.g. stop the sidecar process in a local dev setup).
2. Confirm the still-running indicator stays honest (still shows in-progress, does
   not show any fabricated new lines) and that Phase 129 reattach still recovers the
   real result once the sidecar is reachable again.

## Non-goals to spot-check (do not implement if seen)

- No full terminal / interactive stdin appears anywhere in this feature.
- No second WebSocket frame type is added for run output (see
  `contracts/workspace-run-events.md`).
- No completion push fires while the client is connected and watching live output.
