# core/

Shared infrastructure packages. These packages contain no personal-assistant domain
logic — only the framework primitives that every other package builds on.

**Rule:** a `core/` package may never import from `plugins/` or `apps/`.

Packages are grouped into tiers by role. Each tier is a plain directory (not a
package itself) — it exists to make the dependency shape legible, not to add
another import boundary.

Package READMEs follow [docs/package-readme-template.md](../docs/package-readme-template.md).
Tests run from the repo root via `make test-<short-name>`. See [docs/testing.md](../docs/testing.md).

---

## Packages by tier

| Tier | Packages | Role |
|------|----------|------|
| [kernel/](kernel/) | [ze-logging](kernel/ze-logging/), [ze-data](kernel/ze-data/), [ze-components](kernel/ze-components/) | Zero/near-zero Ze deps — pure infra leaves |
| [contracts/](contracts/) | [ze-agents](contracts/ze-agents/), [ze-communication](contracts/ze-communication/), [ze-plugin](contracts/ze-plugin/), [ze-proactive](contracts/ze-proactive/) | Developer-facing ABCs/protocols the engine implements against |
| [engine/](engine/) | [ze-core](engine/ze-core/) | The orchestration engine itself |
| [seam/](seam/) | [ze-collision](seam/ze-collision/) | Cross-cutting substrate consumed by every domain layer below |
| [cognition/](cognition/) | [ze-memory](cognition/ze-memory/), [ze-correlation](cognition/ze-correlation/), [ze-worldstate](cognition/ze-worldstate/) | Memory, correlation, world-state — the "mind" substrate |
| [automation/](automation/) | [ze-automation](automation/ze-automation/), [ze-skills](automation/ze-skills/) | Goals, workflows, skills — built on cognition |
| [arbitration/](arbitration/) | [ze-priority](arbitration/ze-priority/) | Consumes cognition + automation to rank/order attention |
| [ops/](ops/) | [ze-workspace](ops/ze-workspace/), [ze-onboarding](ops/ze-onboarding/), [ze-ingestion](ops/ze-ingestion/), [ze-seed](ops/ze-seed/), [ze-eval](ops/ze-eval/) | Environment, onboarding, ingestion, seed data, eval |

| Package | Description |
|---------|-------------|
| [ze-logging](kernel/ze-logging/) | Structured logging — `structlog` configuration, `get_logger`, context binding |
| [ze-data](kernel/ze-data/) | Data management — `DataDomain` descriptor and `DataPortabilityService` |
| [ze-components](kernel/ze-components/) | Server-driven UI component descriptors for the React web client |
| [ze-agents](contracts/ze-agents/) | Developer API — `BaseAgent`, `@agent`, `@tool`, shared types, harness hooks |
| [ze-communication](contracts/ze-communication/) | Channel contract — `Channel`/`InboundChannel` ABCs, message types, `ChannelRegistry` |
| [ze-plugin](contracts/ze-plugin/) | Plugin framework — `ZePlugin`, channels, signals, `ZeIntegration` protocol |
| [ze-proactive](contracts/ze-proactive/) | Job scheduling — `ProactiveScheduler`, `ProactiveJob`, push log |
| [ze-core](engine/ze-core/) | LangGraph orchestration, routing, capability gate, OpenRouter, telemetry |
| [ze-collision](seam/ze-collision/) | Contribution collision detection — cross-function conflict logging |
| [ze-memory](cognition/ze-memory/) | Memory persistence and retrieval — facts, episodes, graph, consolidation |
| [ze-correlation](cognition/ze-correlation/) | Cross-domain hypothesis formation from the memory graph |
| [ze-worldstate](cognition/ze-worldstate/) | Open-loop substrate — active concerns, drift detection, evidence-linked confidence |
| [ze-automation](automation/ze-automation/) | Goal + workflow engines, accountability — planners, executors, schedulers |
| [ze-skills](automation/ze-skills/) | Agent Skills — import, review, matching, tool-narrowing |
| [ze-priority](arbitration/ze-priority/) | Attention arbitration — `PriorityView`, shared push budget, user-directed priority override |
| [ze-workspace](ops/ze-workspace/) | Isolated computer — files, shell, skill scripts |
| [ze-onboarding](ops/ze-onboarding/) | Plugin-extensible onboarding coordinator and reset domain types |
| [ze-ingestion](ops/ze-ingestion/) | Content ingestion pipeline — fetch, process, extract, and archive any external content |
| [ze-seed](ops/ze-seed/) | Dev data seeder — curated narrative fixtures for local development |
| [ze-eval](ops/ze-eval/) | Eval infrastructure — runner, judge, verifier, MCP server |

`ze-browser` and `ze-notifications` moved to [`integrations/`](../integrations/) —
they're thin external-service wrappers (browser sidecar, ntfy), the same shape as
`integrations/ze-google`, not core infra.

## Dependency graph

```
ze-logging        ←  no ze deps                                              kernel/
ze-data           ←  no ze deps                                              kernel/
ze-components     ←  no ze deps                                              kernel/
ze-agents         ←  ze-logging                                              contracts/
ze-communication  ←  ze-agents                                               contracts/
ze-plugin         ←  ze-agents, ze-data                                      contracts/
ze-proactive      ←  ze-agents                                               contracts/
ze-core           ←  ze-agents, ze-plugin                                    engine/
ze-collision      ←  ze-agents, ze-plugin, ze-logging                        seam/
ze-memory         ←  ze-agents, ze-plugin, ze-collision                      cognition/
ze-correlation    ←  ze-agents, ze-logging, ze-memory, ze-plugin, ze-collision cognition/
ze-worldstate     ←  ze-agents, ze-proactive, ze-memory, ze-data, ze-components, ze-correlation, ze-plugin, ze-collision  cognition/
ze-automation     ←  ze-agents, ze-logging, ze-proactive, ze-memory, ze-data, ze-components  automation/
ze-skills         ←  ze-agents, ze-proactive, ze-logging, ze-data            automation/
ze-priority       ←  ze-agents, ze-proactive, ze-worldstate, ze-automation, ze-correlation, ze-plugin, ze-collision  arbitration/
ze-workspace      ←  ze-agents, ze-logging, ze-data                          ops/
ze-onboarding     ←  ze-agents                                               ops/
ze-ingestion      ←  ze-agents, ze-memory, ze-browser                        ops/
ze-seed           ←  ze-memory, ze-automation, ze-core, ze-logging, ze-onboarding  ops/
ze-eval           ←  no ze deps                                              ops/
```

The plugin entry point (`ze-sdk`) lives in [`packages/ze-sdk`](../packages/ze-sdk/).

## Where new code goes

| New code | Package |
|----------|---------|
| New agent execution primitive (`BaseAgent` hook, `@tool` behavior) | `ze-agents` |
| New plugin seam (`ZePlugin` hook, channel type, signal contract) | `ze-plugin` |
| New infrastructure primitive (router, gate, graph node) | `ze-core` |
| New memory retrieval policy, graph predicate, or consolidation strategy | `ze-memory` |
| New cross-domain correlation logic | `ze-correlation` |
| New server-driven UI component type | `ze-components` |
| New setup-flow primitive or onboarding provider contract | `ze-onboarding` |
| New eval runner, judge, or verifier | `ze-eval` |
| New outbound/inbound channel contract | `ze-communication` |
| New goal, workflow, or accountability primitive | `ze-automation` |
| New open-loop lifecycle, extraction, or surfacing logic | `ze-worldstate` |
| New skill import, matching, or review primitive | `ze-skills` |
| New cross-function collision detection rule | `ze-collision` |
| New attention-arbitration or priority-override logic | `ze-priority` |
| New dev fixture / seed domain | `ze-seed` |

If the code has any dependency on personal-assistant domain concepts (goals,
workflows, contacts, persona), it does not belong here.

## Signal pipeline

Plugin-emitted signals feed cross-domain correlation:

```
plugins (SignalSource)  →  ze-api (collect + dedupe)  →  ze-memory (admission + ingest)
                                                              ↓
                                                         ze-correlation (hypotheses)
```

Implement `SignalSource` in plugins that produce time-stamped domain events worth correlating. See `specs/phases/060-signal-source-contract/spec.md`.
