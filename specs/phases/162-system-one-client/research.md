# Research: System One Client

**Feature**: `162-system-one-client`
**Date**: 2026-09-30

## 1. OpenRouter hosts Jev; do not add a TypeSafe key

**Decision:** Call Jev through OpenRouter’s native System One API: `POST {openrouter_base_url}/systemone` (production `https://openrouter.ai/api/v1/systemone`). Pin model `typesafe/jev-1.13`. Authenticate with the existing `OPENROUTER_API_KEY`. Do not add `TYPESAFE_API_KEY`, `typesafe-sdk`, or a second billing line.

**Rationale:** Constitution VII is one LLM gateway and one billing key. OpenRouter now implements TypeSafe’s System One request/response shape and bills Jev to the OpenRouter account. A native TypeSafe SDK would be a per-feature vendor and would contradict the user’s plan pin.

**Alternatives considered:**
- TypeSafe-native SDK + `TYPESAFE_API_KEY` (original 162 draft FR-010). Rejected: second key, second vendor, and OpenRouter already exposes the same wire.
- Tunnel judgments through `LLMClient.complete` / chat completions. Rejected: Jev is not a chat model; chat will not return typed `noul`/`choice`/`score`.
- OpenRouter Decisions API (`POST /api/alpha/decisions`). Rejected: alpha surface; the user pinned System One + `typesafe/jev-1.13`.

This is a **Principle VIII hard-cut** of spec FR-010 and of the arch note’s `TYPESAFE_API_KEY` / “must not tunnel through OpenRouter” lines. Generative calls still stay on `LLMClient` + chat. Judgments use a **sibling** client on the same OpenRouter account and a **different** HTTP path.

## 2. Sibling Protocol, 080 pattern

**Decision:** `SystemOneClient` lives in `ze_agents` next to `NLIClient`, not as methods on `LLMClient`. Engine implementation in `ze_core` (same layer as `OpenRouterClient` / `LocalNLIClient`). Re-export from `ze_sdk`. Constructor-inject via `dep_map` and `config["configurable"]["system_one_client"]`. Plugins type against the Protocol and never import `ze_core`.

**Rationale:** Copy phase 080. Mixing typed judgments into `complete()` would force every LLM mock to grow System One fields and would let plugins treat Jev as a chat model.

**Alternatives considered:** One mega-protocol; `OpenRouterClient` secretly implementing both Protocols without a named System One type. Rejected: wrap-then-replace of `LLMClient`, harder fakes.

## 3. HTTP: official SDK if present, else httpx POST

**Decision:** Prefer `OpenRouter.system_one.create(...)` when the pinned `openrouter` package exposes it (same `api_key`, `server_url`, referer, title as chat). `openrouter==0.9.1` in-tree does **not** expose `system_one`. Implement with `httpx.AsyncClient` posting JSON to `{base_url}/systemone`, and add `httpx==0.28.1` on `ze-core` (already pinned elsewhere in the workspace). If a later SDK bump lands `system_one.create`, swap internally without changing the Protocol.

**Rationale:** Chat already uses the official SDK; System One is a different resource. Raw httpx keeps 162 unblocked. Do not wait on an SDK bump to ship the Protocol.

**Alternatives considered:** Bump `openrouter` in this phase solely for `system_one`. Optional during implement if a nearby pin is drop-in; not required. TypeSafe SDK pointed at OpenRouter’s base URL. Rejected: extra dependency and `TYPESAFE_API_KEY` footgun.

## 4. Fail-open inside `evaluate`, not a caller-optional helper

**Decision:** `SystemOneClient.evaluate(state, questions) -> SystemOneResult` never raises into the graph for timeout, missing key, 429/529, 5xx, or transport errors. Those return `outcome="skip"` plus a closed `skip_reason`. Empty/invalid request (no questions, empty state) is rejected **before** the network and also skipped. When `system_one.enabled` is false, inject a disabled client that skips immediately with `skip_reason="disabled"`.

**Rationale:** Spec US2. Same posture as `live_rerank`. A separate helper callers can forget would leak exceptions in 163/164.

**Alternatives considered:** Raise `OpenRouterError` / `RateLimitError` like chat. Rejected: chat failures already have graph handling; a new optional vendor must not become a new outage class. Fail-closed on 162. Rejected: no production consumer yet; fail-closed belongs only to a later high-harm interrupt if ever.

## 5. Config default off; surfaces reserved

**Decision:** `config.yaml` gains:

```yaml
system_one:
  enabled: false
  model: typesafe/jev-1.13
  timeout_ms: 2000
  surfaces: {}
```

`surfaces` is a reserved map for 163/164 flags (`speech_act`, `routing`, …). 162 does not read surface flags to change admission or routing. Secret remains `OPENROUTER_API_KEY` in `.env` (already present). No new env var.

**Rationale:** FR-004 / FR-009. Existing installs do not call Jev. Pin the OpenRouter slug, not `jev-1.13.0` (TypeSafe-native id) and not `~typesafe/jev-latest` (alias moves under calibrated thresholds).

**Alternatives considered:** Default enabled. Rejected: no production questions; would spend and add latency for nothing. Pin dated snapshot `typesafe/jev-1.13-20260917`. Rejected: OpenRouter maps `typesafe/jev-1.13`; the **trace** stores the `model` the API returned.

## 6. Trace field only; no table

**Decision:** Add `MessageTrace.judgments: list[JudgmentTrace]` (default `[]`). `record_trace` copies `state["judgments"]` (default empty). `make_graph_input` sets `judgments: []` each turn so checkpointed lists do not leak. REST `MessageTraceResponse` and WS `WsTraceUpdateFrame` gain the same field. Regenerated `@ze/client`. Trace panel section renders when the list is non-empty. No Alembic.

**Rationale:** FR-007. JSONB on `messages.trace` already exists. 162 may only persist empty lists in production.

**Alternatives considered:** New `judgment_log` table. Rejected: explainability already lives on the message. Graph node just for judgments. Rejected: spec says no new node.

## 7. Cost telemetry is optional but cheap

**Decision:** On a successful (`outcome="ok"`) call, `CostTracker.record` with the **reported** model id, `prompt_tokens=usage.input_tokens`, `completion_tokens=usage.output_tokens` (output is billed at $0; still record the count), `generation_id=response.id`. Skips do not write cost rows.

**Rationale:** Same tracker as chat; Jev still burns OpenRouter credits on input. Do not invent a second cost store.

**Alternatives considered:** Skip cost until 163. Acceptable but worse: silent spend. Reconciler changes. Out of scope unless `fetch_generation_cost` already works for `gen-dec-*` ids (implement may log and ignore if the generations API does not support them).

## 8. Primitive names match the wire

**Decision:** Question `type` values are `noul`, `choice`, `score` (TypeSafe / OpenRouter). Domain dataclasses use those names. Do not invent `yes_no`. Protocol answers expose `noul`, `choice`, `score`, `probabilities`, `confidence` as on the wire. `JudgmentTrace` stores a flattened, JSON-safe copy plus `consumed` and `skip_reason`.

**Rationale:** 163/164 authors copy cookbook questions without a translation layer.

**Alternatives considered:** Ze-only names (`yes_no`) mapped in the client. Extra confusion next to doctrine `Confidence`.

## 9. No production behavior in 162

**Decision:** No caller in extractor, router, skills, retrieval, push, or dream. Disabled client on the configurable is enough for 163 to start. No `@tool` that sends state to System One.

**Rationale:** FR-009. The client is the product of this phase.
