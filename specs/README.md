# Ze Specs

Design and implementation specs for the Ze personal AI assistant.

## Structure

```
specs/
├── phases/            ← feature specs, one spec-kit directory per feature
│   └── NNN-<name>/    ←   spec.md (+ plan.md, research.md, tasks.md, contracts/, …)
├── core/              ← ze-core infrastructure layer specs
└── arch/              ← architecture decision records
```

Feature specs follow the [GitHub spec-kit](https://github.com/github/spec-kit)
workflow (see [arch/spec-kit-adoption.md](arch/spec-kit-adoption.md)). Scaffolding
lives in `.specify/`; the pipeline runs as Claude Code skills.

## Writing a new spec

| What you are writing | How | Destination |
|----------------------|-----|-------------|
| New feature or phase | `/speckit-specify <description>` | `phases/NNN-<name>/spec.md` |
| New ze-core module | follow an existing `core/ze-*.md` spec | `core/<name>.md` |
| Cross-cutting design decision | follow an existing ADR in `arch/` | `arch/<name>.md` |

**Feature pipeline** (spec-kit): `/speckit-specify` → `/speckit-clarify` (optional,
de-risk ambiguity) → `/speckit-plan` (plan + research + data-model + contracts) →
`/speckit-tasks` → `/speckit-analyze` (optional consistency check) →
`/speckit-implement`. Numbering continues the phase sequence automatically
(three-digit, next free number). The project constitution that plans are checked
against lives in `.specify/memory/constitution.md`.

**Required sections by type:**
- Feature: whatever `.specify/templates/spec-template.md` generates — user scenarios, requirements, success criteria
- ADR: Context and Problem Statement, Considered Options, Decision Outcome
- Core: Purpose, Responsibilities, Out of Scope

**Status is authoritative in the spec header.** The index tables below are
navigation aids — update both, but when they diverge the spec header wins.

All Open Questions / `[NEEDS CLARIFICATION]` markers must be resolved (or
explicitly deferred with a target date) before setting status → Implemented.

## Phase specs (`phases/`)

Legend: ✅ Implemented · 🔄 In Progress · 🔲 Pending (spec header `Draft` or `Ready to implement`) · ⏸ Deferred · ⚠️ Deprecated

| # | Spec | Status |
|---|------|--------|
| 00 | [Overview](phases/000-overview/spec.md) | ✅ Current |
| 01 | [Routing](phases/001-routing/spec.md) | ✅ Implemented |
| 02 | [Capability Gate](phases/002-capability-gate/spec.md) | ⚠️ Deprecated → `core/03` |
| 03 | [Memory](phases/003-memory/spec.md) | ✅ Implemented |
| 04 | [Agents](phases/004-agents/spec.md) | ⚠️ Deprecated → `core/01` |
| 05 | [Orchestration](phases/005-orchestration/spec.md) | ✅ Implemented |
| 06 | [OpenRouter Client](phases/006-openrouter-client/spec.md) | ✅ Implemented |
| 07 | [API](phases/007-api/spec.md) | ✅ Implemented |
| 08 | [Telegram Bot](phases/008-telegram/spec.md) | ✅ Implemented |
| 09 | [Agent & Tool API](phases/009-agent-tool-api/spec.md) | ✅ Implemented |
| 10 | [Google Calendar + Gmail](phases/010-phase3-google/spec.md) | ✅ Implemented |
| 11 | [Persona](phases/011-persona/spec.md) | ✅ Implemented |
| 12 | [Workflow](phases/012-workflow/spec.md) | ✅ Implemented |
| 13 | [Memory Consolidation](phases/013-phase5-memory/spec.md) | ✅ Implemented |
| 14 | [User Profile](phases/014-user-profile/spec.md) | ✅ Implemented |
| 15 | [Proactive Ze](phases/015-proactive-ze/spec.md) | ✅ Implemented |
| 16 | [Insight Generation](phases/016-insight-generation/spec.md) | ✅ Implemented |
| 17 | [Cost Telemetry](phases/017-cost-telemetry/spec.md) | ✅ Implemented |
| 18 | [Cost-Aware Routing](phases/018-cost-aware-routing/spec.md) | ✅ Implemented |
| 19 | [Multimodal Input](phases/019-multimodal-input/spec.md) | ✅ Implemented |
| 20 | [Contacts](phases/020-contacts/spec.md) | ✅ Implemented |
| 21 | [Telegram Commands](phases/021-telegram-commands/spec.md) | ✅ Implemented |
| 22 | [Reminders Agent](phases/022-reminders-agent/spec.md) | ✅ Implemented |
| 23 | [Eval](phases/023-eval/spec.md) | ✅ Implemented |
| 24 | [Agentic Tool Loop](phases/024-agentic-tool-loop/spec.md) | ✅ Implemented |
| 25 | [Persona Profiles + Dials](phases/025-persona-profiles/spec.md) | ✅ Implemented |
| 26 | [Prospecting Agent](phases/026-prospecting-agent/spec.md) | ✅ Implemented |
| 27 | [Channels](phases/027-channels/spec.md) | ✅ Implemented |
| 28 | [Goal Engine](phases/028-goal-engine/spec.md) | ✅ Implemented |
| 29 | [Progress Messages](phases/029-progress-messages/spec.md) | ✅ Implemented |
| 30 | [Agent Harness](phases/030-agent-harness/spec.md) | ✅ Implemented |
| 31 | [Goal Engine v2](phases/031-goal-engine-v2/spec.md) | ✅ Implemented |
| 32 | [Goal Collaboration](phases/032-goal-collaboration/spec.md) | ✅ Implemented |
| 33 | [Proactive Goal Suggestions](phases/033-goal-suggestions/spec.md) | ✅ Implemented |
| 34 | [Stuck Goal Detection](phases/034-stuck-goal-detection/spec.md) | ✅ Implemented |
| 35 | [Cross-Goal Output Reuse](phases/035-cross-goal-output-reuse/spec.md) | ✅ Implemented |
| 36 | [Cross-Goal Learning Promotion](phases/036-cross-goal-learning-promotion/spec.md) | ✅ Implemented |
| 37 | [News Package](phases/037-news-package/spec.md) | ✅ Implemented |
| 38 | [News Personalization](phases/038-news-personalization/spec.md) | ✅ Implemented |
| 39 | [News Credibility](phases/039-news-credibility/spec.md) | ✅ Implemented |
| 40 | [Notifications](phases/040-notifications/spec.md) | ✅ Implemented |
| 41 | [Component Descriptors](phases/041-component-descriptors/spec.md) | ✅ Implemented |
| 42 | [Native UI Foundation](phases/042-native-ui-foundation/spec.md) | ✅ Implemented |
| 43 | [React Web App](phases/043-react-web-app/spec.md) | ✅ Implemented |
| 44 | [Calendar Package Split](phases/044-package-split-google-calendar-api/spec.md) | ✅ Implemented |
| 46 | [Accountability Layer](phases/046-accountability-layer/spec.md) | ✅ Implemented |
| 47 | [Plugin Framework](phases/047-plugin-framework/spec.md) | ✅ Implemented (tool namespacing deferred) |
| 48 | [Ze Core Split](phases/048-core-split/spec.md) | ✅ Implemented |
| 49 | [Ze SDK](phases/049-ze-sdk/spec.md) | ✅ Implemented |
| 50 | [News Preference Model](phases/050-news-preferences/spec.md) | ✅ Implemented |
| 51 | [Onboarding Platform](phases/051-onboarding/spec.md) | ✅ Implemented |
| 52 | [Session-Grouped Episode Consolidation](phases/052-session-grouped-consolidation/spec.md) | ✅ Implemented |
| 53 | [Eval Consolidation](phases/053-eval-consolidation/spec.md) | ✅ Implemented |
| 54 | [Progress Messages](phases/054-progress-messages/spec.md) | ✅ Implemented |
| 55 | [Signal Substrate](phases/055-signal-substrate/spec.md) | ✅ Implemented |
| 56 | [Salience & Relevance Model](phases/056-salience-relevance-model/spec.md) | ✅ Implemented |
| 57 | [Correlation Engine](phases/057-correlation-engine/spec.md) | ✅ Implemented |
| 58 | [Inline Conversational Correlation](phases/058-inline-correlation/spec.md) | ✅ Implemented |
| 59 | [Proactive Correlation Push](phases/059-proactive-correlation-push/spec.md) | ⏸ Deferred (post-v1) |
| 60 | [Cross-Plugin Signal Contract](phases/060-signal-source-contract/spec.md) | ✅ Implemented |
| 61 | [Convergence & Pressure Points](phases/061-convergence-pressure-points/spec.md) | 🔲 Pending (design-only) |
| 62 | [Data Portability](phases/062-data-portability/spec.md) | ✅ Implemented |
| 63 | [Integration Framework](phases/063-integration-framework/spec.md) | ✅ Implemented |
| 64 | [Plugin Package Extraction](phases/064-plugin-package-extraction/spec.md) | ✅ Implemented |
| 65 | [Eager Session Summaries](phases/065-eager-session-summaries/spec.md) | ✅ Implemented |
| 66 | [Primitive UI](phases/066-primitive-ui/spec.md) | ✅ Implemented |
| 67 | [Finance Plugin](phases/067-finance-plugin/spec.md) | ✅ Implemented |
| 68 | [ze-data Package](phases/068-ze-data/spec.md) | ✅ Implemented |
| 69 | [ze-ingestion Pipeline](phases/069-ze-ingestion/spec.md) | ✅ Implemented |
| 70 | [Finance Recurring Detection](phases/070-finance-recurring/spec.md) | ✅ Implemented |
| 71 | [Cross-Goal Awareness](phases/071-cross-goal-awareness/spec.md) | ✅ Implemented |
| 72 | [API Client Codegen](phases/072-api-client-codegen/spec.md) | ✅ Implemented |
| 73 | [API Surface](phases/073-api-surface/spec.md) | ✅ Implemented |
| 74 | [Automation Substrate](phases/074-automation-substrate/spec.md) | ✅ Implemented |
| 75 | [Server-Driven UI Package](phases/075-server-driven-ui-package/spec.md) | ✅ Implemented |
| 76 | [ze-api Shell Cleanup](phases/076-ze-api-shell-cleanup/spec.md) | ✅ Implemented |
| 77 | [ze-logging Package](phases/077-ze-logging/spec.md) | ✅ Implemented |
| 78 | [Dream Memory](phases/078-dream-memory/spec.md) | ✅ Implemented |
| 79 | [NLI Cross-Encoder Integration](phases/079-nli-model/spec.md) | ✅ Implemented |
| 80 | [NLI Client + Plugin Access](phases/080-nli-client/spec.md) | ✅ Implemented |
| 81 | [Plugin NLI Adoption](phases/081-plugin-nli-adoption/spec.md) | ✅ Implemented |
| 82 | [ze-web FSD Restructure](phases/082-ze-web-fsd/spec.md) | ✅ Implemented |
| 83 | [ze-communication + ze-messenger](phases/083-ze-communication/spec.md) | ✅ Implemented |
| 84 | [Webhook Infrastructure](phases/084-webhooks/spec.md) | 🔲 Pending |
| 85 | [Ze Messaging Hub](phases/085-messaging-hub/spec.md) | ✅ Implemented |
| 87 | [Plugin UI Platform](phases/087-plugin-ui/spec.md) | ✅ Implemented |
| 88 | [Memory Feed](phases/088-memory-feed/spec.md) | ✅ Implemented |
| 89 | [Message Trace](phases/089-message-trace/spec.md) | ✅ Implemented |
| 90 | [Ze's Mind Split-Pane](phases/090-ze-mind-split-pane/spec.md) | ✅ Implemented |
| 91 | [Goal Dashboard v2](phases/091-goal-dashboard-v2/spec.md) | ✅ Implemented |
| 92 | [Agent Activity Heatmap](phases/092-agent-activity-heatmap/spec.md) | ✅ Implemented (route and chart removed by 190) |
| 93 | [Temporal Memory Timeline](phases/093-temporal-memory-timeline/spec.md) | ✅ Implemented |
| 94 | [Memory Graph View](phases/094-memory-graph-view/spec.md) | ✅ Implemented |
| 95 | [Unified Streaming Architecture](phases/095-live-trace-streaming/spec.md) | ✅ Implemented |
| 96 | [Dev Data Seeder](phases/096-dev-data-seeder/spec.md) | ✅ Implemented |
| 97 | [Embedding Model Upgrade (MiniLM → E5)](phases/097-embedding-model-upgrade/spec.md) | ✅ Model shipped — remainder [160](phases/160-e5-routing-confidence/spec.md) Implemented |
| 98 | [Workflow Run Chat](phases/098-workflow-run-chat/spec.md) | 🔄 In Progress |
| 99 | [Multi-Conversation Support](phases/099-multi-conversation/spec.md) | ✅ Transport shipped — remainder [159](phases/159-concurrent-thread-identity/spec.md) |
| 100 | [Data Dashboard](phases/100-data-dashboard/spec.md) | 🔄 In Progress |
| 101 | [Session Search & Titles](phases/101-session-search/spec.md) | ✅ Implemented |
| 102 | [Workflow Conditional Branching](phases/102-workflow-branching/spec.md) | ✅ Implemented |
| 103 | [Model Default with Overrides](phases/103-model-default-overrides/spec.md) | ✅ Implemented |
| 104 | [Workflow Flowchart View](phases/104-workflow-flowchart-view/spec.md) | ✅ Implemented |
| 105 | [Notification Center](phases/105-notification-center/spec.md) | ✅ Implemented |
| 106 | [Memory Retrieval Relevance](phases/106-memory-retrieval-relevance/spec.md) | ✅ Implemented |
| 107 | [Workflow Resilience and Control](phases/107-workflow-resilience/spec.md) | ✅ Implemented |
| 108 | [Workflow Revision Audit](phases/108-workflow-revision-audit/spec.md) | ✅ Implemented |
| 109 | [Open-Loop Substrate](phases/109-open-loop-substrate/spec.md) | ✅ Implemented |
| 110 | [Open-Loop Drift Detection & Surfacing](phases/110-open-loop-drift-surfacing/spec.md) | ✅ Implemented |
| 111 | [Claim Topology](phases/111-claim-topology/spec.md) | ✅ Implemented |
| 112 | [Session Context Continuity](phases/112-session-context-continuity/spec.md) | ✅ Implemented |
| 113 | [Proactive/Concurrency Hardening Sweep](phases/113-hardening-sweep/spec.md) | ✅ Implemented |
| 114 | [Agent Skills](phases/114-agent-skills/spec.md) | ✅ Implemented |
| 115 | [Workspace Environment](phases/115-workspace-sidecar/spec.md) | ✅ Implemented |
| 116 | [Workspace Follow-Through](phases/116-workspace-follow-through/spec.md) | ✅ Implemented (User Story 4's busy rule delivered by 129) |
| 117 | [Web UI HIG Audit Fixes](phases/117-web-hig-fixes/spec.md) | ✅ Implemented |
| 118 | [Chart Visualization](phases/118-chart-visualization/spec.md) | ✅ Implemented |
| 119 | [Memory Graph Charts](phases/119-memory-graph-charts/spec.md) | ✅ Implemented |
| 120 | [Usage Dashboard Charts](phases/120-usage-dashboard-charts/spec.md) | ✅ Implemented |
| 121 | [Memory Feed Charts](phases/121-memory-feed-charts/spec.md) | ✅ Implemented |
| 122 | [Data Overview Charts](phases/122-data-overview-charts/spec.md) | ✅ Implemented |
| 123 | [Attention Arbitration](phases/123-attention-arbitration/spec.md) | ✅ Implemented |
| 124 | [Contribution Seam Core](phases/124-contribution-seam-core/spec.md) | ✅ Implemented |
| 125 | [Contribution Seam Extension](phases/125-contribution-seam-extension/spec.md) | ✅ Implemented |
| 126 | [Contribution Collision Detection](phases/126-contribution-collision-detection/spec.md) | ✅ Implemented |
| 127 | [User-Directed Priority Override](phases/127-priority-override/spec.md) | ✅ Implemented |
| 128 | [Social Cognition Foundation](phases/128-social-cognition-foundation/spec.md) | ✅ Implemented |
| 129 | [Workspace Run Journal](phases/129-workspace-run-journal/spec.md) | ✅ Implemented |
| 130 | [Social Cognition Co-Occurrence](phases/130-social-cognition-co-occurrence/spec.md) | ✅ Implemented |
| 131 | [Workspace Live Output](phases/131-workspace-live-output/spec.md) | ✅ Implemented |
| 132 | [Priority Turn Surfacing](phases/132-priority-turn-surfacing/spec.md) | ✅ Implemented |
| 133 | [Perception Facts Seam](phases/133-perception-facts-seam/spec.md) | ✅ Implemented |
| 134 | [Memory Facts Hard-Cut](phases/134-memory-facts-hard-cut/spec.md) | ✅ Implemented |
| 135 | [Action Record Ledger](phases/135-action-record-ledger/spec.md) | ✅ Implemented |
| 136 | [Action Instrumentation](phases/136-action-instrumentation/spec.md) | ✅ Implemented |
| 137 | [Evidence-Backed Goal Learning](phases/137-evidence-backed-learning/spec.md) | ✅ Implemented |
| 138 | [Governed Procedure Lifecycle](phases/138-procedure-lifecycle/spec.md) | ✅ Implemented |
| 139 | [Governed Procedure Activation](phases/139-procedure-activation/spec.md) | ✅ Implemented |
| 140 | [Memory Admission + Remember/Forget](phases/140-memory-admission/spec.md) | ✅ Implemented |
| 141 | [Memory Read Contract + Prompt Constitution](phases/141-memory-prompt-constitution/spec.md) | ✅ Implemented |
| 142 | [Speech-Act Routing Across Stores](phases/142-speech-act-routing/spec.md) | ✅ Implemented |
| 143 | [Earned Memory Confirmations and Precise Forget](phases/143-memory-claim-honesty/spec.md) | ✅ Implemented |
| 144 | [Constraint Veto on Gated Writes](phases/144-constraint-veto-mail-calendar/spec.md) | ✅ Implemented |
| 145 | [Response-Level Unsolicited Recitation](phases/145-unsolicited-recitation/spec.md) | ✅ Implemented |
| 146 | [Forget vs Cancel Across Stores](phases/146-forget-vs-cancel/spec.md) | ✅ Implemented |
| 147 | [Ingest vs Remember Honesty](phases/147-ingest-remember-honesty/spec.md) | ✅ Implemented |
| 148 | [Extractor Dual-Write and Dedup Races](phases/148-extractor-dual-write/spec.md) | ✅ Implemented |
| 149 | [Specialist Memory Constitution](phases/149-specialist-memory-constitution/spec.md) | ✅ Implemented |
| 150 | [Eval `memory_proposals_count` Hard-Cut and Guide Phase-Index Honesty](phases/150-eval-guide-honesty/spec.md) | ✅ Implemented |
| 151 | [Fat Delegate ACI](phases/151-fat-delegate-aci/spec.md) | ✅ Implemented |
| 152 | [Per-Delegate Capability and Confirmation](phases/152-per-delegate-gate/spec.md) | ✅ Implemented |
| 153 | [Sequential Routing Hard-Cut](phases/153-sequential-routing-hard-cut/spec.md) | ✅ Implemented |
| 154 | [Conductor Observability and Eval](phases/154-conductor-observability-eval/spec.md) | ✅ Implemented |
| 155 | [Mixed Gather+Act → Conductor](phases/155-mixed-gather-act-conductor/spec.md) | ✅ Implemented |
| 156 | [Conductor Stall / Replan](phases/156-conductor-stall-replan/spec.md) | ✅ Implemented |
| 157 | [Promote Conductor Instance to Workflow/Goal](phases/157-promote-conductor-instance/spec.md) | ✅ Implemented |
| 158 | [Parallel Per-Subtask Gates](phases/158-parallel-subtask-gates/spec.md) | ✅ Implemented |
| 159 | [Concurrent Thread Identity](phases/159-concurrent-thread-identity/spec.md) | ✅ Implemented |
| 160 | [E5 Routing Confidence](phases/160-e5-routing-confidence/spec.md) | ✅ Implemented |
| 161 | [Workspace Chat-First](phases/161-workspace-chat-first/spec.md) | ✅ Implemented |
| 162 | [System One Client](phases/162-system-one-client/spec.md) | ✅ Implemented |
| 163 | [Speech-Act System One](phases/163-speech-act-system-one/spec.md) | ✅ Implemented (conversation path superseded by 173) |
| 164 | [Routing Choice After E5](phases/164-routing-choice-after-e5/spec.md) | ✅ Implemented |
| 165 | [Assistant Response Feedback and Retry](phases/165-response-feedback-retry/spec.md) (split from [117](phases/117-web-hig-fixes/spec.md) US9) | ✅ Implemented |
| 166 | [System One Skill Gating](phases/166-skill-suggestion-system-one/spec.md) | ✅ Implemented |
| 167 | [Routing Choice Criteria](phases/167-routing-choice-criteria/spec.md) | ✅ Implemented (surface enabled) |
| 168 | [Loop Extraction Gate](phases/168-loop-extraction-gate/spec.md) | ✅ Implemented (surface enabled; conversation path superseded by 173) |
| 169 | [Loop Track Tool](phases/169-loop-track-tool/spec.md) | ✅ Implemented |
| 170 | [Executive Repair](phases/170-executive-repair/spec.md) | ✅ Implemented |
| 171 | [Loop Confirmation](phases/171-loop-confirmation/spec.md) | ✅ Implemented |
| 172 | [Corroboration Promotion](phases/172-corroboration-promotion/spec.md) | ✅ Implemented |
| 173 | [Commitment Intake](phases/173-commitment-intake/spec.md) | ✅ Implemented (surface enabled) |
| 177 | [Interruption Governor](phases/177-interruption-governor/spec.md) | ✅ Implemented |
| 180 | [Retry Rollback](phases/180-retry-rollback/spec.md) | ✅ Implemented |
| 181 | [Irreversible Write Confirmation](phases/181-irreversible-write-confirmation/spec.md) | ✅ Implemented |
| 182 | [Complexity Routing](phases/182-complexity-routing/spec.md) | ✅ Implemented |
| 183 | [Web Shell and Tokens (W1)](phases/183-web-shell-tokens/spec.md) | ✅ Implemented |
| 184 | [Composed Answers and Claim Posture (B1)](phases/184-composed-answers-posture/spec.md) | ✅ Implemented |
| 185 | [World Data Gaps (B2)](phases/185-world-data-gaps/spec.md) | ✅ Implemented |
| 186 | [World (W2)](phases/186-web-world/spec.md) | ✅ Implemented |
| 187 | [Ask / Assemble (W3)](phases/187-web-ask-assemble/spec.md) | 🔲 Ready to implement (after 184, 195, 186) |
| 188 | [Doing (W4)](phases/188-web-doing/spec.md) | 🔲 Ready to implement (with 183 + 184; reminders after 185, screen context after 195) |
| 189 | [Mind (W5)](phases/189-web-mind/spec.md) | ✅ Implemented |
| 190 | [Governance (W6)](phases/190-web-governance/spec.md) | ✅ Implemented |
| 191 | [Plugins in Places (W7)](phases/191-web-plugins-in-places/spec.md) | 🔲 Draft |
| 192 | [Voice Input Transport (B3)](phases/192-voice-transport/spec.md) | 🔲 Ready to implement (parallel; before 193) |
| 193 | [Voice and Polish (W8)](phases/193-web-voice-polish/spec.md) | 🔲 Draft |
| 194 | [Accountability Surfaces (B4)](phases/194-accountability-surfaces/spec.md) | 🔲 Ready to implement (parallel; zc040 to reserve) |
| 195 | [Screen Context Awareness](phases/195-screen-context-awareness/spec.md) | ✅ Implemented (live eval: first run 10 of 26, chat_about 9 of 15 after owner routing; chip capture deferred to 193) |

## Ze Core specs (`core/`)

One spec per package in `core/`. The old numbered specs (01–09) are stale — they
describe the pre-split monolithic `ze-core` and are kept only as historical reference.

### Current package specs

| Package | Spec | What it owns |
|---------|------|-------------|
| `ze-core` | [ze-core.md](core/ze-core.md) | Orchestration engine — routing, graph, capability, telemetry, container |
| `ze-agents` | [ze-agents.md](core/ze-agents.md) | Developer API — `@agent`, `BaseAgent`, `@tool`, `LLMClient`, error hierarchy |
| `ze-plugin` | [ze-plugin.md](core/ze-plugin.md) | Plugin extension framework — `ZePlugin` ABC, entry points, lifecycle hooks |
| `ze-sdk` | [ze-sdk.md](core/ze-sdk.md) | Plugin entry point — flat re-export of everything plugin authors need |
| `ze-proactive` | [ze-proactive.md](core/ze-proactive.md) | Job scheduling — `ProactiveJob`, `ProactiveScheduler`, push log |
| `ze-memory` | [ze-memory.md](core/ze-memory.md) | Memory stack — facts, episodes, graph, consolidation, dream |
| `ze-automation` | [ze-automation.md](core/ze-automation.md) | Automation — goals, workflows, accountability, GoalAgent, WorkflowAgent |
| `ze-communication` | [ze-communication.md](core/ze-communication.md) | Channel contract — `Channel` ABC, `InboundChannel`, `ChannelRegistry` |
| Smaller packages | [ze-smaller-packages.md](core/ze-smaller-packages.md) | ze-logging, ze-notifications, ze-browser, ze-data, ze-components, ze-correlation, ze-eval, ze-onboarding, ze-ingestion, ze-seed |

### Legacy specs (stale — pre-split, for historical reference only)

| # | Spec | What it described |
|---|------|------------------|
| 01 | [Agent Decorator & BaseAgent](core/01-agent.md) | `@agent` + `BaseAgent` inside old `ze_core` |
| 02 | [AppInterface](core/02-app-interface.md) | `AppInterface` ABC inside old `ze_core` |
| 03 | [Capability Gate](core/03-capability-gate.md) | `CapabilityGate` inside old `ze_core` |
| 04 | [Routing](core/04-routing.md) | `EmbeddingRouter` inside old `ze_core` |
| 05 | [Orchestration Graph](core/05-orchestration.md) | LangGraph graph inside old `ze_core` |
| 06 | [Memory](core/06-memory.md) | Memory before `ze-memory` extraction |
| 07 | [Container](core/07-container.md) | DI container inside old `ze_core` |
| 08 | [Contacts](core/08-contacts.md) | Contacts primitive before `ze-personal` |
| 09 | [Conversation Persistence](core/09-conversation.md) | Session/message store |

## Architecture decisions (`arch/`)

### Foundational choices

These are the load-bearing decisions that shape the entire codebase. Every contributor
should read them before changing anything structural.

| ADR | Decision |
|-----|----------|
| [**Ze Doctrine**](arch/ze-doctrine.md) | **Constitutional.** Ze's continuous spine is the world-state (model of you + active concerns); epistemic ontology (identity/fact/inference/suspicion/priority); provenance + arbitration order. Every spec is checked against it. See also [Cognitive Architecture](../docs/cognitive-architecture.md). |
| [Pre-v1 Hard Cuts](arch/pre-v1-hard-cuts.md) | **Accepted.** Until a versioned v1, breaking APIs and schemas is the default. No shims, dual-write, or wrap-then-replace across phases. Expires at v1. |
| [Aperture Decision](arch/aperture-decision.md) | **Open decision brief.** Which projection of the world-state the executive layer optimises for — open loops vs life-graph + intervention. Grounds the executive-layer phase spec. |
| [Contribution Seam](arch/contribution-seam.md) | **Shipped through step 7.** Perception facts (Phase 133), `memory_facts` doctrine (Phase 134), ActionRecord ledger and producer instrumentation (135–136), evidence-backed goal learning (Phase 137). Collision detection done (Phase 126). Ranking via `PriorityView` + turn surfacing (123/127/132). Remaining: `signal_sources()` rewiring, real cross-function arbitration (step 8). |
| [Single-User Model](arch/single-user-model.md) | No `user_id` anywhere; auth is a single API key; Ze serves one person |
| [OpenRouter Gateway](arch/openrouter-gateway.md) | All LLM calls through OpenRouter only — single billing, config-driven model swaps |
| [System One Models](arch/system-one-models.md) | **Living.** Typed judgments (Choice/Noul/Score) as an extra decision layer beside OpenRouter and local E5/NLI. First slices: [162](phases/162-system-one-client/spec.md)–[164](phases/164-routing-choice-after-e5/spec.md). Not a package spec. |
| [LangGraph Orchestration](arch/langgraph-orchestration.md) | LangGraph + AsyncPostgresSaver — durable graph execution with confirmation-flow pause/resume |
| [Local Embeddings](arch/local-embeddings.md) | `paraphrase-multilingual-MiniLM-L12-v2` in-process — zero cost, multilingual, hot-path safe |
| [Dataclasses over Pydantic](arch/dataclasses-over-pydantic.md) | `@dataclass` in all domain code; Pydantic only in `ze_api/api/schemas.py` |
| [Alembic Raw SQL](arch/alembic-raw-sql.md) | Hand-written SQL migrations; per-package chains; no ORM |
| [asyncpg + psycopg2 split](arch/asyncpg-psycopg2-split.md) | asyncpg for runtime, psycopg2 for Alembic CLI — asyncpg has no sync mode |
| [ntfy Push Notifications](arch/ntfy-push-notifications.md) | Self-hostable REST-based push; no vendor approval; deep-link support |

### Structural decisions

Made when a significant restructuring forced the question.

| ADR | Decision |
|-----|----------|
| [Package Reorg](arch/package-reorg.md) | Monorepo split: ze-core / ze-personal / ze / ze-browser |
| [Plugin Agents](arch/plugin-agents.md) | ZePlugin ABC, domain agent migration to ze-personal |
| [Monorepo Layout](arch/monorepo-layout.md) | Dissolve `packages/`; promote `core/`, `plugins/`, `apps/` to repo root |
| [Memory Package Extraction](arch/memory-package-split.md) | Hard-cut memory into `ze_memory` with module-specific retrieval, explicit task state, and no shim |
| [Memory Graph Augmentation](arch/memory-graph-augmentation.md) | Add bounded, provenance-first relationships and traversal inside `ze_memory` |
| [Dream Memory](arch/dream-memory.md) | Offline wake/sleep/dream/morning consolidation loop; staging buffer + critic-gated promotion |
| [Correlation Engine](arch/correlation-engine.md) | Bounded relevance-gated correlation over a shared signal/graph substrate; not a world model |
| [Communication Hub](arch/communication-hub.md) | Channel identity contract, thread ownership, memory contribution policy, signal filtering, extensibility |
| [Plugin UI](arch/plugin-ui.md) | Three-tier plugin UI model (SDUI, manifest + generic shell, optional frontend modules) |
| [spec-kit Adoption](arch/spec-kit-adoption.md) | Feature specs use GitHub spec-kit (`specs/phases/NNN-<name>/` dirs, `.specify/` scaffolding, `/speckit-*` pipeline) |
| [Attention Arbitration](arch/attention-arbitration.md) | One ranked `PriorityView` + one shared attention budget across loops, goals, and correlation hypotheses — shipped as Phase 123/127 |
| [Memory Honesty Roadmap](arch/memory-honesty-roadmap.md) | **Living.** After Phase 143: constraint veto (P5), reply-path recitation, forget vs cancel, ingest honesty, extractor dual-write/classifier, specialist constitution, eval field hard-cut, guide index drift |
| [Companion Conductor Roadmap](arch/companion-conductor-roadmap.md) | **Living.** One speaker, one conductor; 151–158 Implemented. Adjacent remainders: 159 (99 thread identity), 160 (97 E5 confidence). Promote is a workflow or goal instance, not a procedure. Directory 151 is conductor ACI, not memory-honesty item 151 (bundled in phase 150). |
| [Social Cognition](arch/social-cognition.md) | **Open decision brief.** People/projects/relationships as evolving state extending the memory graph, not a new store; reconciles an existing parallel `contact_relationships` table into it |
