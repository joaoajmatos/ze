# ze-web Feature-Sliced Design — Spec

> **Package:** `apps/ze-web`
> **Phase:** 82
> **Status:** Implemented

---

## Purpose

Restructure the React web client to **Feature-Sliced Design (FSD)** with six layers and strict import rules. ze-web is growing (finance pages, goal detail views, legal, richer settings). The current mix of fat `pages/*` and partial `features/` will not scale.

Supersedes the package layout section in [43-react-web-app.md](../043-react-web-app/spec.md). Developer guide: [docs/frontend.md](../../docs/frontend.md).

---

## Responsibilities

- Enforce six FSD layers: `app` → `pages` → `widgets` → `features` → `entities` → `shared`
- Each slice exposes a public API via `index.ts`; internal `ui/`, `api/`, `model/` are private
- Route definitions and lazy loading live only in `app/router/`
- Navigation metadata (label, icon, mobile visibility) is derived from the route registry
- ESLint (`@feature-sliced/eslint-config`) enforces layer import boundaries in CI
- REST types stay in `@ze/client`; entity query hooks wrap the generated SDK

---

## Out of Scope

- Next.js or file-based App Router migration
- A `services/api/` layer on top of `@ze/client`
- Central `src/hooks/` or `src/types/` directories
- Finance/legal page implementations (only `entities/transaction` scaffold)

---

## Layer rules

| Layer | Imports from | Named by |
|-------|--------------|----------|
| `app` | `pages`, `shared`, `widgets` (bootstrap only) | — |
| `pages` | `widgets`, `shared` | route segment (`goals`, `chat`) |
| `widgets` | `features`, `entities`, `shared` | UI block role (`chat-workspace`) |
| `features` | `entities`, `shared` | verb phrase (`send-chat-message`) |
| `entities` | `shared` | singular noun (`goal`, `message`) |
| `shared` | nothing above | — |

---

## Package layout

```
apps/ze-web/src/
├── app/
│   ├── App.tsx
│   ├── providers.tsx
│   ├── bootstrap-ws.ts
│   ├── styles/globals.css
│   └── router/
│       ├── index.tsx
│       ├── routes.ts
│       └── lazy.ts
├── pages/
│   ├── chat/
│   ├── goals/
│   ├── contacts/
│   ├── reminders/
│   ├── costs/
│   ├── news/
│   └── settings/
├── widgets/
│   ├── app-shell/
│   ├── chat-workspace/
│   ├── goals-overview/
│   ├── contacts-overview/
│   ├── reminders-overview/
│   ├── costs-overview/
│   ├── news-overview/
│   ├── settings-workspace/
│   ├── context-overlay/
│   └── onboarding-wizard/
├── features/
│   ├── send-chat-message/
│   ├── respond-to-confirmation/
│   ├── switch-chat-session/
│   ├── load-chat-history/
│   ├── export-user-data/
│   ├── import-user-data/
│   ├── delete-user-data/
│   ├── test-api-connection/
│   ├── invalidate-on-ws-refresh/
│   └── send-context-notice/
├── entities/
│   ├── goal/
│   ├── contact/
│   ├── reminder/
│   ├── news-article/
│   ├── cost-entry/
│   ├── message/
│   ├── session/
│   ├── primitive-tree/
│   └── transaction/
└── shared/
    ├── ui/
    │   ├── primitives/   # button, input, sheet
    │   └── layout/       # PageHeader, ListPage, EmptyState, …
    ├── lib/
    ├── api/
    ├── config/
    └── effects/
```

---

## Router contract

`app/router/routes.ts` declares paths, lazy page imports, and nav meta. Only `app/` references URLs. Pages are code-split via `React.lazy`.

Onboarding remains an app-level gate in `App.tsx` (not a route).

---

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `@ze/client` | Generated REST + WS types and SDK functions |
| `@ze/ui` / `@ze/ui/react` | Server-driven UI contract and renderer |
| `@feature-sliced/eslint-config` | Layer boundary linting |
| `@tanstack/react-query` | REST caching in entity query hooks |
| `zustand` | Session, overlay, WS connection state |

---

## Success criteria

- `make lint-web` passes with FSD import rules
- `make test-web` passes
- No management page duplicates list-page boilerplate (`shared/ui/layout/ListPage`)
- New domain adds entity + widget + page slices without touching unrelated code
