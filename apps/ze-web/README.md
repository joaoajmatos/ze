# ze-web

React web client for Ze. Connects to `ze-api` over WebSocket for chat, renders server-driven UI components, and has five places: World, Ask, Doing, Mind, and Governance.

Architecture: [Feature-Sliced Design](https://feature-sliced.design/). See [docs/frontend.md](../../docs/frontend.md) and [specs/phases/082-ze-web-fsd/spec.md](../../specs/phases/082-ze-web-fsd/spec.md).

## Role in Ze

`ze-web` is the user's window into Ze. All conversational interaction happens here over WebSocket; the other places read the REST API via `@myguyze/ze-client`. Server-driven UI components from agents render in the Ask canvas without requiring frontend deploys. Plugins add modules to places, never pages.

## Source layout

```
src/
├── app/           # bootstrap, router, providers, global styles
├── pages/         # thin route entry points (one slice per route)
├── widgets/       # composite screen sections
├── features/      # user actions (export-data, turn-stream, …)
├── entities/      # domain nouns (goal, message, contact, …)
└── shared/        # UI kit, lib, API wiring, config
```

| Path | What it provides |
|------|------------------|
| `app/router/routes.tsx` | Route table — the five places and redirects from old paths |
| `shared/styles/ze.css` | Design tokens and shell classes ([DESIGN.md](../../DESIGN.md) is the design source) |
| `widgets/app-shell/` | The frame around every place: top bar, strip, Presence, Ask bar, phone bottom bar |
| `features/ask-bar/` | The Ask bar and the state of the Ask overlay |
| `entities/conversation/`, `features/turn-stream/` | One store per thread and the one handler for the conversation frames |
| `widgets/assemble/` | The Assemble canvas, the trace rail, confirmations and Retry in place, and the Ask overlay |
| `pages/ask/` | The Ask page: canvas and trace; the try chips and conversations are portalled into the shell rail under the orb, as World does |
| `entities/message-trace/` | Per-message trace query and the trace UI pieces the trace rail uses |
| `entities/message-feedback/`, `features/reply-feedback/`, `features/retry-reply/` | Thumbs up/down, Retry, and their reasons on assistant replies |
| `features/primitive-tree/` | Server-driven UI renderer and its WebSocket actions |
| `shared/api/ws-client.ts` | WebSocket singleton |
| `shared/config/` | Server URL + API key (`localStorage`) |

## Dependencies

Stack: React 19, Vite, TypeScript, Tailwind CSS, TanStack Query, Zustand, `@myguyze/ze-client`, `@myguyze/ze-ui`.

## Running

```bash
make web          # bun dev server on :5173
make web-build    # production build
make dev-full     # backend + web app together
```

Configure server URL and API key in the onboarding flow or in Governance › Connections. No `VITE_*` env vars.

## Quality

```bash
make test-web     # vitest
make lint-web     # ESLint (FSD import boundaries)
```

See [docs/testing.md](../../docs/testing.md). WebSocket protocol: [docs/native-interface.md](../../docs/native-interface.md).
