# @myguyze/ze-ui

Server-driven UI contract, validators, and React renderer for Ze.

## Role in Ze

Agents describe UI as trees of primitives (text, table, form, stat row, card, and others). `ze-components` builds these trees in Python. This package defines the same contract in TypeScript, checks incoming trees, and renders them in React. The contract layer has no framework dependency.

### Key features

- Types for every primitive, generated from the `ze-components` JSON schema
- `parsePrimitiveTree` and `validatePrimitiveTree` check a tree at runtime and throw `PrimitiveValidationError` on bad input
- `PrimitiveRenderer` and `PrimitiveTreeRenderer` render parsed trees. The host app handles transport (WebSocket sends, onboarding state)
- Claim primitives: `headline`, `claim_card`, and `claim_timeline` render a stored record with its posture. A card's line shows the claim kind, state, confidence and a slipped flag. Tone follows the posture: a slipped item is hot, an item that needs the user is cream, and a suspicion or inference has a dotted edge
- Card actions go to the host through `CardActionEvent` (`intent`, `ref_id`, `subject`). The host decides what each intent does
- Typed actions: a button, card action, claim-list item or table row action carries a `PrimitiveAction` (`ask`, `tool`, `navigate` or `compose`). The host handles it through `onAction`. A row action fills `"{key}"` in a tool action's args from the row's key
- Tolerant parsing: `parsePrimitiveTree(data, { version })` checks each node. A known type must be valid. An unknown type becomes a fallback node that renders as a table of its scalar fields. A tree with no version, or a 1.x version, parses in legacy mode: a string-action button renders disabled ("This older button no longer works."). A legacy tree that cannot parse throws `PrimitiveLegacyError`
- Shared fixtures in `fixtures/` (each with an `.expect.json`) are checked by pytest and vitest. In development, the `/dev/primitives` route in `ze-web` renders them all
- Chart primitives under `@myguyze/ze-ui/charts` (area, bar, line, and pie)

### Integration

`apps/ze-web` renders chat components and plugin modules with this package. Run `make codegen` after you change a `ze-components` primitive. The command rewrites `src/generated/`. A tag that matches `pkg-v*` publishes the package to GitHub Packages.

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

## Styling the renderer

The renderer ships Tailwind defaults and carries no app CSS. A host restyles it through the actions object:

```typescript
const actions = {
  classNames: { heading: "app-heading", badge: "app-badge", card: "app-card" },
  renderHeadline: (text) => <DotMatrix text={text} />,
};
<PrimitiveTreeRenderer nodes={nodes} actions={actions} />
```

- `classNames` maps a part (`heading`, `subheading`, `body`, `label`, `caption`, `code`, `muted`, `badge`, `card`, `table`, `steps`, `connections`, `button`, `buttonPrimary`, `buttonDanger`, `claimCard`, `claimTimeline`, `divider`) to a class. A mapped part replaces the default classes. An unmapped part keeps them, so a host without a map looks as before.
- `renderHeadline` draws the `headline` primitive. Without it, the text renders as plain type.
- `onChatAbout` shows the "Chat about this" chip on a claim card and receives a `ChatAboutEvent`.

## Testing

From the repo root:

```bash
make test-web
```

See [docs/testing.md](../../docs/testing.md).
