# Feature Specification: System One Client

**Feature Branch**: `162-system-one-client`

**Created**: 2026-09-30

**Status**: Implemented

**Input**: User description: "First System One slice: Protocol sibling of NLIClient, engine client, DI, config, MessageTrace judgments, fail-open. No production behavior change when disabled. Governed by specs/arch/system-one-models.md."

**Governed by**: [`specs/arch/system-one-models.md`](../../arch/system-one-models.md), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md), [`specs/arch/openrouter-gateway.md`](../../arch/openrouter-gateway.md), constitution Principles III, V, VII, VIII. Pattern: Phase [080](../080-nli-client/spec.md).

**Depends on**: Nothing in-tree beyond existing `NLIClient` / `LLMClient` DI. OpenRouter System One (`typesafe/jev-1.13`) is an optional runtime behind `system_one.enabled`, billed to `OPENROUTER_API_KEY`.

**Does not start**: Speech-act judge (163), routing Choice (164), skills, retrieval classify, loops, push, dream, plugins.

---

## Overview

Ze has two injected cognitive clients today: a generative `LLMClient` (OpenRouter) and a local entailment `NLIClient`. It has no place to put a **typed judgment** (closed labels + probabilities) that code can threshold.

This phase adds that place and wires it so later phases can call it. With the feature **off** or the key missing, every turn behaves as today. With it **on**, the client can be called from tests and a no-op production surface; **no admission or routing behavior changes here**.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The engine can ask a typed question and get a typed answer (Priority: P1)

A maintainer (or a later phase) asks one yes/no, one closed-set, or one graded question over a small named state. The answer is a probability or a chosen label plus how peaked the distribution is — not a paragraph to parse.

**Why this priority**: Without a client, 163 and 164 cannot exist. This is the MVP.

**Independent Test**: Unit tests inject a fake client; they never call a live vendor. A real-shaped response object is readable (choice / noul / score fields).

**Acceptance Scenarios**:

1. **Given** a fake client that returns a yes-probability of 0.9 for a named question, **When** the caller asks that question, **Then** it reads 0.9 without parsing JSON text from an LLM.
2. **Given** a fake client that returns a closed-set label with a probability map, **When** the caller asks that question, **Then** it sees the label, the full map, and a peakedness number.
3. **Given** the Protocol is imported from the plugin SDK, **When** a plugin module type-hints the Protocol, **Then** it does not import the engine package.

---

### User Story 2 - A missing vendor or a timeout does not change the turn (Priority: P1)

The judgment service is down, slow, unconfigured, or rate-limited. The user still gets a reply. Memory admission and routing keep using their current judges.

**Why this priority**: Single-user assistant; a new vendor must not be a new outage class.

**Independent Test**: Client configured to raise or sleep past timeout; the caller receives a skip result and the existing path runs.

**Acceptance Scenarios**:

1. **Given** no API key, **When** a turn runs with System One enabled in config, **Then** the turn completes on the pre-162 path and a skip is logged.
2. **Given** the client times out or returns 429/529, **When** a caller uses the standard fail-open helper, **Then** it does not raise into the graph.
3. **Given** System One disabled in config, **When** a turn runs, **Then** the client is not required and no judgment records appear on the trace.

---

### User Story 3 - A turn can show what was judged (Priority: P2)

After a later phase consumes judgments, the existing message explainability surface can list them: which question, which answer, whether code used it, which model id answered.

**Why this priority**: Doctrine wants honest provenance. Unused speculative answers must be distinguishable from consumed ones.

**Independent Test**: Construct a trace with one consumed and one unused judgment; the stored structure keeps both and marks which was consumed.

**Acceptance Scenarios**:

1. **Given** a completed turn that recorded judgments, **When** the trace is loaded, **Then** each record has question id, primitive kind, answer, probabilities when applicable, peakedness when applicable, model id, token count, latency, and consumed flag.
2. **Given** a speculative question whose answer was ignored, **When** the trace is shown, **Then** it is marked not consumed.
3. **Given** a skip (timeout / no key), **When** trace is recorded, **Then** the skip is visible rather than a fake high-confidence answer.

---

## Edge Cases

- Config enabled but key missing: skip, do not crash at process start if the rest of the app can run (dev without `OPENROUTER_API_KEY`).
- Alias vs pinned model: config MUST pin `typesafe/jev-1.13` (not `jev-latest`); the trace stores the id the service reported, not only the alias.
- Empty question map or empty state: reject in code before the network; do not send.
- Default unit tests and CI: never call the live vendor (Principle V).
- Plugin authors MUST NOT gain an agent tool that dumps arbitrary session state into the judgment service in this phase.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose a constructor-injected judgment client Protocol, sibling to the existing NLI and LLM clients, not an extension of the LLM client.
- **FR-002**: Plugin code MUST type against that Protocol via the public SDK and MUST NOT import the engine to use it.
- **FR-003**: The engine MUST own the HTTP (or equivalent) implementation. Plugins MUST NOT ship a second vendor SDK.
- **FR-004**: Configuration MUST include an enable flag, a pinned model identifier, a timeout, and room for later per-surface flags. Default MUST be disabled or fail-open so existing installs do not change behavior.
- **FR-005**: The API key MUST live in environment secrets, not committed YAML.
- **FR-006**: Callers MUST treat timeout, missing key, and vendor overload as skip: existing behavior, structured log, no graph failure.
- **FR-007**: The per-message explainability record MUST be able to store a list of judgments with the fields in User Story 3. This phase MAY record empty lists only; later phases populate them.
- **FR-008**: Default automated tests MUST mock the client. Live vendor calls MUST be opt-in and marked slow if added at all.
- **FR-009**: This phase MUST NOT change speech-act admission, routing, skill match, retrieval, push, or dream behavior.
- **FR-010**: Generative LLM calls MUST remain on OpenRouter via `LLMClient` (chat completions). Typed judgments MUST use OpenRouter’s native System One endpoint (`POST /api/v1/systemone`) with model `typesafe/jev-1.13` and the existing `OPENROUTER_API_KEY`. They MUST NOT use chat completions, MUST NOT add a TypeSafe-native API key, and MUST NOT add `typesafe-sdk`.

### Key Entities

- **Judgment request**: Named state (small JSON) plus a map of named questions (yes/no, closed set, or ordered levels).
- **Judgment answer**: Per question: selected label or yes-probability or level position; optional full distribution; optional peakedness; model id; usage.
- **Judgment skip**: Structured “not used” outcome (no key, timeout, error) distinct from a real answer.
- **Trace judgment record**: One stored answer or skip attached to a message, with `consumed`.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of default unit tests for this phase pass with no live vendor network.
- **SC-002**: With the feature disabled, 0 changes to routing envelopes, extracted facts, or skill matches on existing fixtures.
- **SC-003**: With the key missing and the feature enabled, 100% of sampled turns still complete; 0 uncaught client exceptions in the graph.
- **SC-004**: A plugin-facing import of the Protocol does not pull in the engine package (import graph / unit assertion).
- **SC-005**: A constructed trace record can hold at least two judgments and mark exactly one consumed.

---

## Assumptions

- OpenRouter-hosted Jev (`typesafe/jev-1.13`) is the first implementation; the Protocol is vendor-neutral enough for a fake in tests.
- Single-user: the existing OpenRouter key in `.env` is enough; no per-tenant keys and no second vendor secret.
- 162 does not need a new database table; trace JSON is enough.
- Constitution VII is **LLM** gateway uniqueness plus one billing key. System One is not an LLM; OpenRouter’s native `/systemone` path is the allowed judgment transport.

## Out of Scope

- Replacing Haiku speech-act (163).
- Changing E5 routing bars or decompose (164 / 160).
- Agent `@tool` wrappers that send free-form text to the judgment service.
- Calibrating production thresholds (no production questions yet).
- Zero-data-retention contract legal review (record as follow-up; do not block the Protocol).

## Verbatim Constraints

- `SystemOneClient`
- `NLIClient`
- `LLMClient`
- `ze_sdk`
- `OPENROUTER_API_KEY`
- `typesafe/jev-1.13`
- `system_one`
- `MessageTrace`
- `judgments`
- `consumed`
- Principle VII
- Principle VIII
