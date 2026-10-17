# @myguyze/ze-ui

Server-driven UI contract, validators, and React renderer for Ze.

## Role in Ze

Agents describe UI as trees of primitives (text, table, form, progress bar, and others). `ze-components` builds these trees in Python. This package defines the same contract in TypeScript, checks incoming trees, and renders them in React. The contract layer has no framework dependency.

### Key features

- Types for every primitive, generated from the `ze-components` JSON schema
- `parsePrimitiveTree` and `validatePrimitiveTree` check a tree at runtime and throw `PrimitiveValidationError` on bad input
- `PrimitiveRenderer` and `PrimitiveTreeRenderer` render parsed trees. The host app handles transport (WebSocket sends, onboarding state)
- Claim primitives: `headline`, `claim_card`, and `claim_timeline` render a stored record with its posture. A card's line shows the claim kind, state, confidence and a slipped flag. Tone follows the posture: a slipped item is hot, an item that needs the user is cream, and a suspicion or inference has a dotted edge
- Card actions go to the host through `CardActionEvent` (`intent`, `ref_id`, `subject`). The host decides what each intent does
- Chart primitives under `@myguyze/ze-ui/charts` (area, bar, line, and pie)

### Integration

`apps/ze-web` renders chat components and plugin pages with this package. Run `make codegen` after you change a `ze-components` primitive. The command rewrites `src/generated/`. A tag that matches `pkg-v*` publishes the package to GitHub Packages.

## Responsibilities

| Path | What it provides |
|---|---|
| `src/index.ts` | Primitive types, parse and validate functions, errors, `uiSchema` |
| `src/generated/` | JSON schema, types, and validators from `ze_components.schema.export_json_schema()` |
| `src/parse.ts`, `src/errors.ts` | Runtime parsing and validation errors |
| `src/react/` | `PrimitiveRenderer`, `PrimitiveTreeRenderer`, and action context |
| `src/charts/` | Chart components used by the renderer |

## Dependencies

`ajv`, `visx`, `d3`, `motion`, and a few UI helpers. `react` and `react-dom` are peer dependencies. No Ze packages.

## Usage

```typescript
import { parsePrimitiveTree } from "@myguyze/ze-ui";
import { PrimitiveTreeRenderer } from "@myguyze/ze-ui/react";

const nodes = parsePrimitiveTree(rawComponents);
<PrimitiveTreeRenderer nodes={nodes} actions={actions} />
```

## Testing

From the repo root:

```bash
make test-web
```

See [docs/testing.md](../../docs/testing.md).
