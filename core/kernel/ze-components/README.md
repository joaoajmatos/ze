# ze-components

Server-driven UI component descriptors for Ze. Allows agents to emit structured component payloads that the React web client (`ze-web`) renders without requiring app updates.

## Role in Ze

Text-only responses aren't enough for structured data — goal cards, confirmation forms, metric dashboards, timelines. Agents emit component descriptors during their tool loop; `ze-web` renders them inline with the chat response, so new UI patterns can ship from the backend without a frontend deploy.

### Key features

- Typed component descriptors (cards, forms, tables, timelines, metrics, confirmations)
- JSON schema generation from Python dataclasses for LLM tool schemas
- Claim posture — `claims.py` defines `ClaimPosture`, set by code from a stored record. The `claim` field is on every primitive. Ze omits it from every `render_*` tool schema and drops it with a `render_tool_claim_dropped` warning if a model supplies one
- `headline`, `claim_card`, and `claim_timeline` primitives show what Ze knows, how sure it is, and where it learned it
- Code generation pipeline — `make generate-components` produces schemas and TypeScript types

### Integration

Agents call component tools during execution. A harness hook in `ze-api` collects descriptors from the agentic loop and attaches them to the WebSocket message frame's `components` field. `ze-web`'s `ComponentRenderer` deserialises and renders them.

## Responsibilities

| Module | What it provides |
|---|---|
| `schema.py` | JSON schema generation from Python dataclasses — used to build LLM tool schemas |
| `types.py` | Component descriptor dataclasses |
| `claims.py` | `ClaimPosture`, `Readout`, `CardAction`, `TimelineEntry`, `headline_text()`, `claim_tone()` |
| `context.py` | Component context helpers, including `append_serialized()` for components that are already dicts |
| `tools.py` | Agent tool integration for emitting components |

## Dependencies

Depends on `ze-agents` and `ze-logging`. No third-party runtime dependencies.

`ze-priority` depends on this package to build composed answers.

## Usage

Agents call component tools during execution; the resulting descriptors are serialised and sent as a `components` field in the WebSocket message frame.

```python
from ze_components.types import ComponentDescriptor

descriptor = ComponentDescriptor(type="goal_card", props={"title": "...", "status": "active"})
```

## Code generation

Component schemas are generated from Python dataclasses:

```bash
make generate-components
```

TypeScript types for the web client are generated alongside the JSON schema.

## Testing

From the repo root:

```bash
make test-components
```

See [docs/testing.md](../../docs/testing.md).
