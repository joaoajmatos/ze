# ze-* — Smaller Core Packages

Reference specs for packages that are self-contained enough not to need a full spec.

---

## ze-logging

**Package:** `core/kernel/ze-logging`  
**Purpose:** Configures structlog for the whole system. Exports `get_logger(name)`.
Every Ze package uses this instead of stdlib `logging` or `print`.  
**Rule:** Always `from ze_logging import get_logger; logger = get_logger(__name__)`.

---

## ze-notifications

**Package:** `integrations/ze-notifications`  
**Purpose:** Push notification abstraction over ntfy. `NtfyNotifier` sends HTTP PUT
to `{NTFY_BASE_URL}/{NTFY_TOPIC}`. Used by `ProactiveNotifier` (ze-proactive) and
`NativeAppInterface` (ze-api) when the WebSocket is not connected.  
**See also:** [ADR — ntfy Push Notifications](../arch/ntfy-push-notifications.md)

---

## ze-browser

**Package:** `integrations/ze-browser`  
**Purpose:** Browser sidecar client. `BrowserClient` connects to a Playwright sidecar
process. `browser_tool` is a `@tool` for the prospecting agent to fetch and extract
web page content. No Ze domain knowledge.  
**See also:** [Phase 26 — Prospecting Agent](../phases/026-prospecting-agent/spec.md)

---

## ze-data

**Package:** `core/kernel/ze-data`  
**Purpose:** `DataDomain` Protocol and `DataPortabilityService`. Plugins implement
`DataDomain` to expose their data for export. No Ze domain knowledge.  
**See also:** [Phase 62 — Data Portability](../phases/062-data-portability/spec.md), [Phase 68 — ze-data Package](../phases/068-ze-data/spec.md)

---

## ze-components

**Package:** `core/kernel/ze-components`  
**Purpose:** Server-driven UI component descriptor types and serialisation. Agents
return component descriptors (`atoms/`, `molecules/`, `organisms/`) that the React
client renders. No rendering logic lives here.  
**See also:** [Phase 41 — Component Descriptors](../phases/041-component-descriptors/spec.md), [ADR — Plugin UI](../arch/plugin-ui.md)

---

## ze-correlation

**Package:** `core/cognition/ze-correlation`  
**Purpose:** `CorrelationEngine` — finds non-obvious connections between signals,
facts, and episodes inside the user's neighbourhood. `PostgresHypothesisStore` persists
hypotheses. Recall-tagged: every correlation includes `provenance` marking whether
evidence came from graph recall or live search.  
**See also:** [Phase 57 — Correlation Engine](../phases/057-correlation-engine/spec.md), [ADR — Correlation Engine](../arch/correlation-engine.md)

---

## ze-eval

**Package:** `core/ops/ze-eval`  
**Purpose:** Eval infrastructure — `EvalRunner`, `EvalJudge`, `EvalVerifier`, `EvalScorer`,
YAML scenario loading, MCP server for interactive evals. Connects to ze-api over HTTP;
no internal Ze imports.  
**See also:** [Phase 23 — Eval](../phases/023-eval/spec.md), [docs/eval.md](../../docs/eval.md)

---

## ze-onboarding

**Package:** `core/ops/ze-onboarding`  
**Purpose:** `OnboardingCoordinator` drives first-run setup through a series of
`OnboardingProvider` steps (persona capture, channel setup, goal elicitation).
`PostgresOnboardingStore` persists progress. Can be replayed per-step.  
**See also:** [Phase 51 — Onboarding Platform](../phases/051-onboarding/spec.md)

---

## ze-ingestion

**Package:** `core/ops/ze-ingestion`  
**Purpose:** Ingest pipeline for external content (RSS, emails, documents). Fetchers
pull raw content; processors extract structured signals; the sink writes to ze-memory
and ze-correlation. `IngestionAgent` handles user-triggered ingestion.  
**See also:** [Phase 69 — ze-ingestion Pipeline](../phases/069-ze-ingestion/spec.md)

---

## ze-seed

**Package:** `core/ops/ze-seed`  
**Purpose:** Development data seeder. Generates realistic synthetic facts, episodes,
goals, and conversations for local development and eval. Not imported by any production
package.  
**See also:** [Phase 96 — Dev Data Seeder](../phases/096-dev-data-seeder/spec.md)
