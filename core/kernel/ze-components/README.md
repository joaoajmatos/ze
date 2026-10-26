# ze-components

Server-driven UI component descriptors for Ze. Allows agents to emit structured component payloads that the React web client (`ze-web`) renders without requiring app updates.

## Role in Ze

Text-only responses aren't enough for structured data — goal cards, confirmation forms, metric dashboards, timelines. Agents emit component descriptors during their tool loop; `ze-web` renders them inline with the chat response, so new UI patterns can ship from the backend without a frontend deploy.

### Key features

- Typed component descriptors (cards, forms, tables, timelines, metrics, confirmations)
- JSON schema generation from Python dataclasses for LLM tool schemas
- Claim posture — `claims.py` defines `ClaimPosture`, set by code from a stored record. The `claim` field is on every primitive. Ze omits it from every `render_*` tool schema and drops it with a `render_tool_claim_dropped` warning if a model supplies one
- `headline`, `claim_card`, and `claim_timeline` primitives show what Ze knows, how sure it is, and where it learned it
- Typed actions — `actions.py` defines `AskAction`, `ToolAction`, `NavigateAction` and `ComposeAction`. A `Button.action` takes one of these. A string action raises `InvalidComponentError`. A `ToolAction` names an agent (`owner`) and one of its write tools that opted in with `@tool(ui_action=True)`; the press runs through the normal write gates
- Slot primitives — `entity_facet`, `stat_row`, `claim_list`, `sparkline` and `card`, plus a keyed `table` (`keys`, `row_actions`)
- Render tools for agents: `render_stat_row`, `render_keyed_table` and `render_sparkline` join the older ones. Claim posture and tool, navigate and compose actions never appear in a render tool schema. `render_confirm` and `render_choice_group` keep model-written `value`s as chat choices (`AskAction`)
- `UI_CONTRACT_VERSION` is `"2.0"`. Transports that carry newly built trees send it as `ui_version`
- Code generation pipeline — `make codegen` produces schemas and TypeScript types

### Integration

Agents call component tools during execution. `ComponentCollectionHook` (`hook.py`), registered by `ze-api`, collects descriptors from the agentic loop. `ze-api` attaches them to the WebSocket message frame's `components` field. `PrimitiveRenderer` in `@myguyze/ze-ui` renders them in `ze-web`.

## Responsibilities

| Module | What it provides |
|---|---|
| `schema.py` | JSON schema generation from Python dataclasses — used to build LLM tool schemas |
| `actions.py` | The four typed actions and their bounds |
| `atoms/`, `molecules/`, `organisms/`, `patterns/` | Component descriptor dataclasses and helpers |
| `claims.py` | `ClaimPosture`, `Readout`, `CardAction`, `TimelineEntry`, `headline_text()`, `claim_tone()` |
| `context.py` | Component context helpers, including `append_serialized()` for components that are already dicts |
| `tools.py` | `render_*` agent tools for emitting components |
| `hook.py` | `ComponentCollectionHook` — collects the descriptors a loop emits |
| `serialize.py` | `serialize_primitive` and `serialize_tree` — dataclass to dict, dropping `None` fields |
| `summary.py` | `describe_components` — a short sentence naming what a reply showed, for history and push bodies |

## Dependencies

Depends on `ze-agents` and `ze-logging`. No third-party runtime dependencies.

`ze-priority` depends on this package to build composed answers.

## Usage

Agents call component tools during execution; the resulting descriptors are serialised and sent as a `components` field in the WebSocket message frame.

```python
from ze_components import Card, text
from ze_components.serialize import serialize_tree

tree = serialize_tree([Card(title="Goal", children=[text("On track")])])
```

## Code generation

Component schemas are generated from Python dataclasses:

```bash
make codegen
```

`make codegen` runs `scripts/codegen.ts`. It writes the TypeScript types and validators for `@myguyze/ze-ui` and `@myguyze/ze-client` alongside the JSON schema.

## Testing

From the repo root:

```bash
make test-components
```

See [docs/testing.md](../../docs/testing.md).
