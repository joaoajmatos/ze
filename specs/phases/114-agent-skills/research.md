# Phase 0 Research: Agent Skills

All items below were resolved either by the spec's own Clarifications session
(2026-08-11) or by surveying existing Ze architecture for the closest precedent. No
open `NEEDS CLARIFICATION` markers remain.

## 1. Package placement: new core package vs. plugin

**Decision**: New `core/ze-skills/` package, wired directly into `apps/ze-api` (not a
`ZePlugin`).

**Rationale**: Skills are cross-cutting — every agent, regardless of domain, must be able
to have skill instructions injected and tool access narrowed (FR-020: global scope, no
per-agent assignment). `ze-worldstate` and `ze-automation` establish the precedent for
"core-adjacent domain substrate wired directly by `apps/ze-api`'s composition root, not
routed through the `ZePlugin` graph-node/agent-registration mechanism." A `ZePlugin`
would be the wrong shape here because plugins compose *into* the graph for their own
domain; skills modify how *every* agent's turn is assembled, which is an engine-level
concern layered next to (not inside) any one plugin.

**Alternatives considered**:
- *Fold into `ze-core` directly* — rejected. `ze-core` is documented as pure engine
  infrastructure with "no domain knowledge," and the constitution's layered-architecture
  principle keeps it that way; `ze-worldstate` was extracted from `ze-core` for the same
  reason in phase 109 and is the template to follow, not a precedent to abandon.
  `ze_core` still gets one new node (`match_skills`) but that node is dependency-injected
  (reads `config["configurable"]["skill_matcher"]`) rather than importing `ze_skills`
  directly — identical to how `surface_loops` consumes `loop_surfacer` without `ze_core`
  depending on `ze_worldstate`.
- *A `ZePlugin` (`ze-skills-plugin`)* — rejected. Bundled bundled-in-a-plugin skills are
  still supported (FR-007) via a new `ZePlugin.bundled_skill_paths()` hook, but the skill
  *engine* itself (matching, storage, review, injection) is not plugin-shaped since it has
  no single owning domain and must run before/around every plugin's own agents.

## 2. Automatic matching mechanism

**Decision**: Reuse the `EmbeddingRouter` pattern (`core/ze-core/ze_core/routing/router.py`) —
embed each active skill's `name + description` once (cached, invalidated on
approve/disable/content-change), embed the per-turn message once (or reuse the routing
embedding already computed for agent routing in `embed_route`), cosine-similarity via
matrix-vector product, apply a configurable relevance floor (`skills.match_threshold` in
`config.yaml`, analogous to `RouterConfig.threshold`).

**Rationale**: Resolved via `/speckit-clarify` (2026-08-11): reuses the already-proven
local-embedding pattern, adds no LLM cost per turn, and is consistent with constitution
principle VII (local embeddings, one LLM gateway). Skill descriptions are short text like
agent descriptions, so the same encode/compare mechanics apply directly.

**Alternatives considered**: LLM-based classification — rejected in clarification for
added latency/cost on every turn with active skills, and because embedding similarity is
already the established mechanism for exactly this kind of "does this short text match
this message" decision in Ze (`EmbeddingRouter` itself).

## 3. Explicit invocation syntax

**Decision**: Slash-style syntax, `/skill-name`, parsed from the raw user message text
before/alongside automatic matching.

**Rationale**: Resolved via `/speckit-clarify`. Mirrors invocation syntax already familiar
from Claude Code's own skill system, unambiguous (no fuzzy-match false positives), and
simple to parse (regex against the message text, resolve against active skills' slugified
names).

**Alternatives considered**: Free-text name matching (rejected — ambiguous, harder to
distinguish from prose that merely mentions a skill's name); LLM-inferred intent
(rejected — folds a second LLM decision into routing, adds cost/latency the embedding
path avoids).

## 4. Agent scope

**Decision**: Skills apply globally across all agents — no per-agent assignment
(FR-020).

**Rationale**: Resolved via `/speckit-clarify`. Matches the single-user, single coherent
assistant model — the spec's own framing treats a skill as "an addition to what Ze knows
how to do," not a per-agent capability grant. Keeps the data model simpler (no join table)
and matches FR-008's framing that a skill only *narrows* an agent's existing tools rather
than being scoped to particular agents in the first place.

**Alternatives considered**: Per-agent assignment — rejected in clarification; adds a
join-table and management-UI step without a stated user need, and cuts against "global by
default, narrow only where a skill's own `allowed-tools` says so."

## 5. Source content re-check cadence

**Decision**: Daily proactive job (`SkillRecheckJob`, `@proactive_job`, cron configurable
under `skills.recheck.cron` in `config.yaml`, default e.g. `"0 6 * * *"`) plus
user-triggered manual refresh from the management view (FR-015 already covers the manual
path; FR-021 adds the scheduled path).

**Rationale**: Resolved via `/speckit-clarify`. Matches the existing proactive job cadence
pattern used by `ze-worldstate`'s `StaleSuspicionJob`/`DriftSweepJob` and
`ze-automation`'s `GoalSuggestionJob` — a single daily sweep is proportionate to a
single-user system where content changes are rare and not time-critical to detect within
minutes.

**Alternatives considered**: User-triggered only (no background job) — rejected in
clarification; leaves a stale/changed source undetected indefinitely, which cuts against
SC-004 ("100% of subsequent conversations are shielded from changed content").

## 6. Supporting reference files

**Decision**: Non-script reference files bundled in an imported skill's archive are
fetched and stored (new `skill_reference_files` table, content alongside the skill row)
and made available for injection into context when the skill is used, mirroring how
`resume_recap` and matched-skill instructions are prepended to the system prompt via
`AgentContext`.

**Rationale**: Resolved via `/speckit-clarify`. This matches the open Agent Skills
format's own "progressive disclosure" design (`SKILL.md` frontmatter + body as the
always-loaded layer, supporting files as pull-in-when-relevant reference material) —
storing them now avoids a data-model change later if/when selective reference-file
injection is implemented.

**Alternatives considered**: Parse but don't store — rejected in clarification; would
require re-fetching the archive on every use and loses the "review shows everything that
would be added" guarantee (FR-005) for anything beyond the SKILL.md body itself.

## 7. Tool-access narrowing mechanism

**Decision**: A skill's `allowed-tools` (if present) is intersected — never unioned —
with the invoking agent's own `tools` class attribute, at the single point where
`BaseAgent.agentic_loop` resolves `tool_names` (new `AgentContext.skill_tool_names: list[str]
| None` field, consumed alongside the existing `tool_names` parameter). When multiple
matched skills in the same turn each declare a restriction, the applied set is the
intersection of all of them (most conservative), consistent with "narrow, never expand."

**Rationale**: `agentic_loop` already accepts an optional `tool_names` override
(`core/ze-agents/ze_agents/base_agent.py`); the existing default-to-`self.tools` behavior
is the natural insertion point for a second, narrower default sourced from
`AgentContext`, following exactly the same single-field / single-consumption-site shape
already proven by `resume_recap` (added in phase 112) rather than touching every
individual `@agent` class's `run()` implementation.

**Alternatives considered**: Per-agent enforcement (each `@agent`'s `run()` computes its
own restricted tool list) — rejected as unnecessarily invasive; would require editing
every existing and future agent instead of one shared consumption point.

## 8. Approval / rejection flow shape

**Decision**: REST-based pending→resolved transitions with atomic conditional updates
(`WHERE status = 'pending_review'`), mirroring
`ze_automation.goals.suggestion_store.GoalSuggestionStore.mark_accepted`/`mark_dismissed` —
not the live-conversation `AWAIT_CONFIRMATION`/`pending_confirmations` WebSocket gate.

**Rationale**: Skill approval happens from the management view, out of band from any
particular conversation turn — there is no in-flight graph execution paused waiting for
this decision the way `AWAIT_CONFIRMATION` pauses a turn. The goal-suggestion pattern
(`SuggestionStatus` enum, conditional `UPDATE ... WHERE id = $1 AND status = 'pending'`
returning a boolean) is the direct precedent for a simple, race-safe, non-live approval
decision and needs no new mechanism.

**Alternatives considered**: Reusing `pending_confirmations` — rejected; that table and
its `AWAIT_CONFIRMATION` gate are purpose-built for a graph run paused mid-turn awaiting a
WS reply on the *same* thread, which does not describe skill review at all.

## 9. Skill Usage persistence

**Decision**: No dedicated `skill_usages` table. A new `skills_used: list[SkillUsageTrace]`
field on the existing `MessageTrace` dataclass (`core/ze-core/ze_core/conversation/messages/types.py`),
populated by `record_trace` and persisted via the existing `messages.trace` JSONB column
(phase 89's trace mechanism) and existing `trace_update` WS frame.

**Rationale**: FR-010 requires usage be "retrievable alongside that message's other
explainability information" — that is precisely what `MessageTrace` already is for
`routing_method`, `memory_chunks`, `tool_calls`, etc. Adding a parallel table would
duplicate a join Ze already resolves for free by loading one message's trace.

**Alternatives considered**: A dedicated `skill_usages` table keyed by `(message_id,
skill_id)` — rejected as redundant; nothing in the spec requires querying "which messages
used skill X" independently of the per-message trace view (no such requirement in
Success Criteria or Acceptance Scenarios), so the added join-table complexity isn't
earned. If a future phase needs that query shape, it can be added without touching this
phase's schema.

## 10. Migration ownership

**Decision**: New chain, prefix `zsk`, owned by `core/ze-skills/ze_skills/migrations/`,
registered in `apps/ze-api/ze_api/migrate.py` as `_ZE_SKILLS_VERSIONS` alongside
`_ZE_WORLDSTATE_VERSIONS`/`_ZE_INGESTION_VERSIONS` (direct-wire core packages, not
`ZePlugin.migrations_path()`).

**Rationale**: Matches `CLAUDE.md`'s migration-ownership table exactly — one prefix per
package, filename `{revision}_{feature}.py`, package that owns the Postgres store owns
the chain. `ze-skills` is a directly-wired core package like `ze-worldstate`
(prefix `zw`) and `ze-ingestion` (prefix `zi`), so it gets its own two-to-three-letter
prefix rather than continuing another package's chain.
