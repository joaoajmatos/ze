# @myguyze/ze-client

Typed TypeScript client for the `ze-api` REST API and WebSocket protocol.

## Role in Ze

`ze-web` talks to the backend only through this package. Code generation builds most of it from the FastAPI OpenAPI spec and the WebSocket frame models, so the client cannot drift from the server.

### Key features

- One named function per route, taken from each route's `operation_id` (for example `listGoals()`)
- Request and response types for every route
- Types for every WebSocket frame
- Helpers for file export, archive import, and health checks
- Plugin UI helpers: load plugin pages, settings, and operations by name

### Integration

`apps/ze-web` depends on the package through the Bun workspace. A tag that matches `pkg-v*` publishes it to GitHub Packages. Run `make codegen` after you change a FastAPI route or a WebSocket schema, and commit the result.

## Responsibilities

| Module | What it provides |
|---|---|
| `src/generated/sdk.gen.ts` | Named SDK functions |
| `src/generated/types.gen.ts` | REST request and response types |
| `src/generated/ws.ts` | WebSocket frame types |
| `src/client.ts` | `configure()` and `createZeClient()` |
| `src/blob.ts` | `downloadExport`, `importArchive`, `healthCheck` |
| `src/plugin-ui.ts` | `loadPluginPage`, `loadPluginSettings` |
| `src/sdk-dispatch.ts` | `invokeSdkOperation`, `loadPluginOperation` |
| `src/error.ts` | `ApiError` |

## Dependencies

`@hey-api/client-fetch`. No Ze packages.

## Usage

```typescript
import { configure, listGoals } from "@myguyze/ze-client";

configure({ serverUrl, apiKey });
const { data } = await listGoals();
```

## Testing

From the repo root:

```bash
make test-web
```

See [docs/testing.md](../../docs/testing.md).
