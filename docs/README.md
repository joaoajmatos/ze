# Ze — Documentation

Flat files, grouped here by audience. Start with [Concepts](#concepts) if you are new to Ze; start with [Extending](#extending) if you are adding an agent or plugin.

Design specs (what comes next) live in [`specs/`](../specs/), not here. The constitutional layer is [Ze Doctrine](../specs/arch/ze-doctrine.md).

## Concepts

| Doc | What it covers |
|-----|----------------|
| [cognitive-architecture.md](cognitive-architecture.md) | Seven cognitive functions mapped onto packages |
| [architecture.md](architecture.md) | System overview, LangGraph flow, modules at a glance |
| [package-architecture.md](package-architecture.md) | Monorepo split, `ZePlugin`, where new code belongs |

## Extending

| Doc | What it covers |
|-----|----------------|
| [sdk.md](sdk.md) | `ze_sdk` reference — exports, `BaseAgent`, `@agent` / `@tool`, plugin hooks |
| [extending-ze.md](extending-ze.md) | End-to-end: agents, plugins, proactive jobs, channels |
| [adding-an-agent.md](adding-an-agent.md) | Step-by-step agent authoring |
| [channels.md](channels.md) | Adding an outbound channel (LinkedIn, WhatsApp, …) |
| [package-readme-template.md](package-readme-template.md) | Template for new package READMEs |

## Domains

| Doc | What it covers |
|-----|----------------|
| [memory.md](memory.md) | Facts, episodes, graph, retrieval policies, NLI |
| [dreaming.md](dreaming.md) | Offline sleep/dream loop — staging, critics, journal |
| [goals.md](goals.md) | Goal engine — milestones, gates, conversational usage |
| [workflows.md](workflows.md) | Multi-step plans, scheduling, step execution |
| [scheduled-jobs.md](scheduled-jobs.md) | Background schedule, memory lifecycle, proactive push |
| [ingestion.md](ingestion.md) | Fetchers, processors, extractors, plugin sinks |
| [news.md](news.md) | RSS ingestion, ranking, credibility |
| [finance.md](finance.md) | Data sources, CSV import, categories, privacy, deletion |
| [onboarding.md](onboarding.md) | Plugin-extensible setup, seed review, reset scopes |
| [skills.md](skills.md) | Agent Skills — import, review, matching, scripts in the workspace |
| [data-portability.md](data-portability.md) | Export, import, deletion — `DataDomain` contract |

## Client & ops

| Doc | What it covers |
|-----|----------------|
| [frontend.md](frontend.md) | ze-web — FSD layout, `@ze/client`, plugin UI |
| [native-interface.md](native-interface.md) | WebSocket frames, confirmations, ntfy, unread replay |
| [browser.md](browser.md) | Browser sidecar — Compose, health checks, Fly deploy |
| [workspace.md](workspace.md) | Workspace sidecar — files, shell, skill scripts, modes, Fly deploy |
| [configuration.md](configuration.md) | `.env`, `config.yaml`, `persona.yaml` |
| [deployment.md](deployment.md) | Fly.io, GitHub Actions CI, environment setup |
| [testing.md](testing.md) | `make test-<name>` across Python packages and ze-web |
| [eval.md](eval.md) | End-to-end evals via MCP, LLM-as-judge |
