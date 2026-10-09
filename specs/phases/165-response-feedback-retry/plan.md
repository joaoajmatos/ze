# Implementation Plan: Assistant Response Feedback and Retry

**Branch**: `165-response-feedback-retry` | **Date**: 2026-10-09 | **Spec**: [spec.md](spec.md)

## Summary

Add per-reply thumbs up/down (append-only evidence on the contribution seam) and a text-only Retry. Feedback is a new `ClaimKind.FEEDBACK_RECORD` licensed to Perception, stored in `ze-memory` as `feedback_records` (`zm024`), linked to the message by id. Retry-safety is computed on the server from the trace plus a new required reversibility declaration on every WRITE tool. A retry run executes with write tools blocked and memory admission skipped, then replaces the reply in place and keeps the old one as superseded evidence. v1 builds no rollback and no feedback consumer.

## Technical Context

- **Languages**: Python 3.12 (FastAPI, LangGraph, asyncpg), TypeScript (React, `@ze/client`, vitest).
- **Storage**: Postgres. New table `feedback_records` (ze-memory, `zm024`). New columns on `messages` (ze-core chain, `zc031`).
- **Testing**: package suites via `make test-<name>`; mock asyncpg pools; no real OpenRouter; web tests with vitest; two eval scenarios.
- **Constraints**: pre-v1 hard cuts (no shim for undeclared tools, no dual-write); plugins import `ze_sdk` only; `ze_core` never imported by plugins; `ze-agents` must not import `ze_memory`.

## Constitution / doctrine check

- Doctrine functions: Perception (observes reaction; new licence `FEEDBACK_RECORD`), Action (retry safety reads what Action did), Governance (reversibility gate). Memory is custodian only.
- Contribution seam: new payload goes through `validate_and_submit`. A claim kind outside a function's licence is rejected by the type, same as 124/135.
- Claim vocabulary: provenance `prompt_supplied` (user-stated), confidence 1.0, target face `WORLD` (research R2: evidence about Ze's output, not a claim about the user).
- Pre-v1: undeclared WRITE tool fails registration; old traces without tool metadata are "unknown" and make Retry unavailable. No shim.

## Package ownership

| Concern | Package | Migration |
|---|---|---|
| `ToolReversibility`, `@tool(reversibility=, undo_tool=, undo_note=)`, `ClaimKind.FEEDBACK_RECORD` | `ze-agents` | none |
| Perception licence, `Contribution.feedback_record` payload | `ze-plugin` | none |
| `FeedbackRecord`, store, `submit_feedback_record`, `feedback_records` | `ze-memory` | `zm024` |
| Trace tool metadata, `retry_eligibility`, retry turn, `messages.replaced_by/replaces`, retry-mode (write block, admission skip) | `ze-core` | `zc031` |
| REST routes, WS retry frame, schemas, DataDomain | `ze-api` | none (ze-api owns no tables) |
| Reversibility declarations on every WRITE tool | each owning package | none |
| SDK re-exports | `ze-sdk` | none |
| UI | `ze-web`, `@ze/client` | none |

## Design

### D1. Feedback record
`FeedbackRecord(id, idempotency_key, message_id, thread_id, kind, occurred_at, provenance, confidence, target_face, trace_present, replaced_message_id?)`. `kind` closed: `thumbs_up|thumbs_down|cleared|retry_requested`. Append-only; unique `idempotency_key`; current rating = latest of the three rating kinds by `occurred_at, created_at`. Idempotency key is `feedback:{message_id}:{client_key}` with a client-supplied key (UUID per press); a repeat returns the existing row. No FK to `messages` (messages can be deleted by data deletion; feedback is deleted in the same domain), but writes validate the message exists and is an assistant message.

### D2. Reversibility declaration
`@tool(access=WRITE, reversibility=ToolReversibility.REVERSIBLE, undo_tool="cancel_reminder", undo_note="Does not recall notifications already shown")`. `undo_tool` required for REVERSIBLE and must name a registered tool at startup validation; `IRREVERSIBLE` takes neither. READ tools reject the arguments. Startup check `validate_tool_declarations()` runs in container bootstrap and fails loudly. The inventory in spec.md "Deferred" is the starting classification; `create_event` is `IRREVERSIBLE` in v1 (attendee invites cannot be recalled).

### D3. Trace gets effect metadata
`record_trace` resolves each `ToolCallTrace` against the registry at write time and stores `access`, `reversibility`, `undo_tool`, and `gate` (`none|approved|denied|expired`) so eligibility never depends on the registry state at retry time. Nested delegate tool calls (Phase 151) are flattened into the same list. Unknown tool name → `access="unknown"`. `MessageTrace.effects_known: bool` is true only when the trace was built with this metadata; older traces parse to `False`.

### D4. Retry eligibility (`ze_core/conversation/retry.py`)
Pure function `retry_eligibility(message, trace, latest_assistant_id, thread_busy, pending) -> RetryEligibility`. Rules in order: not assistant/proactive/command → `not_applicable` (no control); pending confirmation → `turn_pending`; not latest → `not_latest`; busy → `busy`; trace missing → `trace_unavailable`; `effects_known` false or any `unknown` → `unknown_tool`; any workspace tool → `workspace_run`; any approved gate on a write → `confirmed_action`; any write with `IRREVERSIBLE` → `has_irreversible_action`; any write with `REVERSIBLE` → `has_reversible_action`; any other write → `has_write_action`. The text lists up to three action names ("set a reminder") from a small tool→phrase map owned by each tool declaration (`effect_phrase` is declared per tool; `undo_note` is for the future undo phase).  Failed write calls still count (partial execution).

### D5. Retry turn
WS frame `{"type":"retry","message_id","thread_id"}` → `handle_retry` (same busy flag as turns). Steps: re-evaluate eligibility server-side → append `retry_requested` feedback → fork graph state to the checkpoint before the original turn (research R1) → run the graph with `config.configurable.retry_mode=True` and the original user text → on success save the new assistant message with `replaces=old`, set old `replaced_by=new`, emit `message` frame for the new reply and `message_superseded` for the old → on failure emit `error` with `code="retry_failed"` and leave everything unchanged.
`retry_mode`: (a) BaseAgent tool dispatch and `delegate_to_agent` refuse WRITE tools with a model-visible message; (b) `capability_check` never produces `AWAIT_CONFIRMATION` for writes because they are refused before gating; (c) `write_memory` skips admission, episode write and dream hooks but still appends to session `messages`; (d) proactive jobs and goal hooks are not triggered.

### D6. Surfaces
REST (new `routes/feedback.py`): `PUT /api/v0/messages/{message_id}/feedback` (`setMessageFeedback`) body `{rating: "up"|"down"|"none", idempotency_key}`; `GET /api/v0/messages/feedback?ids=` (`getMessageFeedback`) returns per message `current`, `history[]`, `retry: {available, reason_code, reason_text}`, `replaces`, `replaced_by`. Existing `GET /messages` hides superseded messages unless `include_superseded=true`; `MessageSchema` gains `replaces`, `replaced_by`. WS in: `retry`. WS out: `message_superseded`, and `error` frames gain optional `code`. Details in [contracts/](contracts/).

### D7. Web
- `entities/message-feedback`: query (batch), set mutation (optimistic), retry-eligibility derived from the same payload.
- `features/reply-feedback`: `ReplyActions` (thumbs, Retry, reason as `aria-describedby` text), mounted through an `actions` slot on `MessageBubble` by `widgets/chat-workspace` (entities may not import features).
- `features/retry-reply`: sends the WS frame, tracks per-thread retrying state, handles `message_superseded` and `retry_failed`.
- `widgets/trace-panel`: `FeedbackSection` in `TraceEntry`: current, history, retried-by / replaces links.
- `@ze/client` and WS schema regenerated via `make codegen`.

### D8. Data and boundaries
`DataDomain` for `feedback_records` (export/delete). No feedback read path in routing, admission, prompts, ranking; a guard test greps the engine packages for `FeedbackStore` imports and asserts the turn graph builds without it in the container deps.

## Research / risks (see research.md)

R1 checkpoint rewind for retry; R2 target face; R3 nested tool-call coverage; R4 hiding superseded messages from model context; R5 WRITE-tool count and classification review; R6 trace retention.

## Project structure (new/changed)

```
core/contracts/ze-agents/ze_agents/{tool.py,claims.py,reversibility.py}
core/contracts/ze-plugin/ze_plugin/contribution.py
core/cognition/ze-memory/ze_memory/feedback_records/{types,store,contribution,errors}.py
core/cognition/ze-memory/ze_memory/migrations/versions/zm024_feedback_records.py
core/engine/ze-core/ze_core/conversation/{retry.py,turn.py}
core/engine/ze-core/ze_core/conversation/messages/{types.py,store.py}
core/engine/ze-core/ze_core/orchestration/nodes/{trace.py,memory.py}
core/engine/ze-core/ze_core/migrations/versions/zc031_message_supersession.py
apps/ze-api/ze_api/api/routes/feedback.py ; ze_api/api/websocket/{endpoint,turns}.py ; schemas.py
apps/ze-web/src/{entities/message-feedback,features/reply-feedback,features/retry-reply,widgets/trace-panel,entities/message/ui}
eval/scenarios/{retry_text_only,retry_refused_after_write}.yaml
```
