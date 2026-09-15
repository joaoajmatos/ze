# Research: Workspace Live Output

## R1: Transport for live output into the conversation and workspace view

**Decision**: The frontend reads `GET /api/v0/workspace/runs/{id}/events` (Phase 129's
existing NDJSON watch endpoint) directly from the browser as a streaming `fetch` body,
once per handle it is currently rendering as in-progress. No new WebSocket frame type,
no new REST endpoint.

**Rationale**: The spec's Verbatim Constraints section already pins this: the phase
"MUST NOT invent a second event contract." The endpoint
(`apps/ze-api/ze_api/api/routes/workspace.py:266-294`) already streams
already-produced lines then live lines as `{"seq", "type", "data"}` NDJSON, closing
after the `exit` event — exactly the replay-then-continue behavior FR-002 asks for.
The existing chat WebSocket (`trace_update` frame, `apps/ze-web/src/entities/message/ui/MessageBubble.tsx:9-35`)
only fires once around graph completion (Phase 90/95); it identifies *that* a run is
`in_progress` and its `id`/`command`, but was never meant to carry a growing byte
stream. Reusing it for live text would mean inventing a second completion/streaming
channel — the thing FR-008 forbids.

**Alternatives considered**:
- Proxy run events onto the main chat WebSocket as new frames — rejected: adds a
  second live-data path duplicating the already-specified NDJSON contract, and the
  workspace page (no per-message WS session) would still need its own reader anyway.
- Poll `GET /runs/{id}` on an interval for `stdout_preview`/`stderr_preview` — rejected:
  those fields are periodic snapshots, not an append-only sequence; the client would
  have to diff previous vs. current preview text itself and could still miss content
  once the server-side cap is hit. The events stream already gives ordered append-only
  chunks with a `seq` for cheap resume/de-dup.

## R2: Preview size bound (FR-005)

**Decision**: No new truncation logic. `sidecar/workspace/supervisor.py` already caps
total emitted journal bytes per run at `OUTPUT_PREVIEW_CHARS` (env
`WORKSPACE_OUTPUT_PREVIEW_CHARS`, default 8000) — both the terminal
`stdout_preview`/`stderr_preview` and the live event stream stop growing once that cap
is hit (`supervisor.py:123,448-449`). This phase's live view inherits that bound for
free by reading the same stream; it does not add a second cap.

**Rationale**: Reusing the Phase 115/129 cap satisfies "matching the existing
preview-size discipline" (FR-005) without a second source of truth for "how much is
too much."

**Alternatives considered**: A separate frontend-side character cap on the rendered
`<pre>` — rejected as redundant; the server already stops emitting past the cap, so a
client cap would only matter for a pathological single-line rendering cost, not for
bounding retained text. If needed at all, it is a defensive render guard, not a
product decision worth its own task.

## R3: Redaction reuse (FR-006)

**Decision**: Reuse `ze_workspace.sanitize.redact()` (already applied server-side to
`stdout_preview`/`stderr_preview` in `client.py:183-184` and `store.py`). The `/events`
NDJSON proxy (`workspace.py:277-293`) currently forwards `event.data` from the sidecar
**unredacted** — it reads straight from the supervisor's journal, which is upstream of
`redact()`. This is a real gap FR-006 requires closing: `data-model.md` and `tasks.md`
must include applying `redact()` to each `stdout`/`stderr` event's `data` field in the
proxy before it is yielded.

**Rationale**: `WorkspaceRunStatusDTO` (terminal preview) already redacts on read
(`client.py`), but the raw per-event stream does not. Confirmed by reading
`watch_workspace_run_events` in `apps/ze-api/ze_api/api/routes/workspace.py:277-293`,
which builds `line["data"] = event.data` directly from `client.watch_run()` with no
`redact()` call.

**Alternatives considered**: Redact at the sidecar (`supervisor.py`) before appending
to the journal — rejected: `redact()` lives in `ze_workspace` (mind-side package) per
existing layering, and the sidecar has no dependency on it; redacting once at the
proxy boundary (already the pattern for the terminal preview fields) keeps the
denylist in one place and matches Phase 115's existing seam.

## R4: Binary / non-printable detection (edge case, not a numbered FR)

**Decision**: No new detection layer. The sidecar already decodes all process output
as `text.decode("utf-8", errors="replace")` (`supervisor.py:335,435-437`), so binary
bytes already arrive as UTF-8 with `U+FFFD` replacement characters rather than raw
bytes. The frontend renders a "output is not printable" note instead of the raw text
for a given handle when the replacement-character ratio in the accumulated preview
crosses a small fixed threshold (e.g. any occurrence beyond a couple of isolated
characters), and always leaves the workspace file linkable regardless.

**Rationale**: Matches the edge case ("Chat does not dump binary... short note...
retrieve the file") without adding a MIME-sniffing dependency; the signal already
exists in the decoded text.

**Alternatives considered**: Sniff the workspace output file's content-type via
`python-magic` or similar — rejected: adds a new dependency for a cosmetic detail the
existing decode-with-replacement already signals cheaply.

## R5: Workspace page consumption pattern

**Decision**: `RunningRunBanner` (`apps/ze-web/src/widgets/workspace-management/ui/RunningRunBanner.tsx`)
gains a small live-output sub-view per in-progress row, driven by the same
`useWorkspaceRunEvents(runId)` hook introduced for chat (R1). `useWorkspaceRunsQuery`
(existing polling list) keeps deciding *which* runs are in progress; the new hook only
supplies the growing text for a run already known to be in progress.

**Rationale**: Keeps one hook, one contract, reused by both surfaces (FR-003 "one
truth, two places"), and avoids widening `WorkspaceRunItem`/`WorkspaceRunListResponse`
with growing text that the list-polling query was never meant to carry.

**Alternatives considered**: Embed live text in the `GET /runs` list response —
rejected: that endpoint is a periodically-refetched list (`useWorkspaceRunsQuery`),
not an append-only stream; cramming growing text into it either re-sends the whole
preview every poll (wasteful, and re-introduces the "duplicate dump" edge case FR
already warns against) or requires the same diffing problem R1 rejected.

## Summary of NEEDS CLARIFICATION resolved

None remained after `/speckit-clarify` — all Technical Context unknowns below are
resolved directly from the existing Phase 129/115 implementation, not from new product
decisions.
