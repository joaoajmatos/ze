# Feature Specification: Agent Skills

**Feature Branch**: `114-agent-skills`

**Created**: 2026-08-11

**Status**: Draft

**Input**: User description: "Agent Skills — standard-compatible skill system for Ze. Users can import skills (from a URL or file) written in the open Agent Skills format, review and approve them before they take effect, and see when Ze uses one during a conversation. Developers can also ship skills bundled inside Ze's own domain packages. Skills add reusable instructions/knowledge to a conversation; they do not grant new tool access beyond what an agent already has, and they cannot bundle executable code in this phase."

## Clarifications

### Session 2026-08-11

- Q: Do active skills apply across every agent uniformly, or does each skill need to be scoped/assigned to specific agents? → A: Global to all agents — no per-agent assignment.
- Q: When a user "explicitly names" a skill in their message (FR-019b), how is that detected? → A: Slash-style syntax (e.g. `/skill-name`), mirroring skill invocation elsewhere in Ze's tooling.
- Q: What mechanism decides automatic skill matching (FR-019a's "relevance threshold")? → A: Embedding similarity — reuse the existing `EmbeddingRouter` pattern (local embeddings, no extra LLM cost).
- Q: How often does Ze re-check an imported skill's source content for changes (User Story 4)? → A: Daily proactive job, consistent with Ze's existing proactive job cadence.
- Q: When an imported skill's archive includes non-script supporting reference files, what happens to them? → A: Stored alongside the skill and made available to be injected into context when the skill is used.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Import a skill from a URL and approve it (Priority: P1)

A user finds a skill published somewhere on the web in the standard Agent Skills format (a `SKILL.md` file with YAML frontmatter, optionally bundled with supporting reference files in a zip). They give Ze the URL. Ze fetches and parses it, then shows the user exactly what the skill would add — its name, its description, and its full instructions — before it can affect any conversation. The user approves it, and it becomes active.

**Why this priority**: This is the core value proposition — without it, there is no way to get any skill (imported or otherwise) into Ze. Everything else is secondary to "get a skill in, safely."

**Independent Test**: Can be fully tested by submitting a URL pointing to a valid `SKILL.md`, confirming the parsed content is displayed for review, approving it, and confirming it now appears in the active skills list.

**Acceptance Scenarios**:

1. **Given** a URL to a valid `SKILL.md` file, **When** the user submits it for import, **Then** Ze fetches and parses the file and presents the parsed name, description, and full instructions for review without activating it.
2. **Given** a skill pending review, **When** the user approves it, **Then** the skill's status changes to active and it becomes eligible for use in future conversations.
3. **Given** a skill pending review, **When** the user rejects it, **Then** the skill is discarded (or retained in a rejected state for the user's records) and never becomes active.
4. **Given** a URL that does not resolve to a valid `SKILL.md` (malformed frontmatter, missing required fields, unreachable URL), **When** the user submits it, **Then** Ze reports a clear parse/fetch error and creates no skill record.
5. **Given** a `SKILL.md` that references bundled executable scripts, **When** it is parsed, **Then** Ze flags the unsupported capability plainly in the review view rather than silently dropping it, and the user can still choose to approve the instructions-only portion.

---

### User Story 2 - See when Ze uses a skill in conversation (Priority: P1)

While chatting with Ze, a user asks something that matches a skill they've approved. Ze uses the skill's instructions to inform its response, and the user can plainly see, attached to that message, which skill was used — not just infer it from a suddenly-different response style.

**Why this priority**: Invisible skill usage defeats the purpose of a reviewed, trusted skill system — the whole point of the review step is trust, and that trust only pays off if usage stays visible turn by turn. This is as core as importing itself.

**Independent Test**: Can be fully tested by approving a skill with a distinctive, checkable instruction (e.g. "always end responses with a specific phrase"), sending a message that should trigger it, and confirming both the behavior and a visible "skill used" indicator appear together on that message.

**Acceptance Scenarios**:

1. **Given** an active skill relevant to a user's message, **When** Ze responds, **Then** the response is visibly annotated with which skill(s) were used for that turn.
2. **Given** no active skill is relevant to a user's message and none was explicitly named, **When** Ze responds, **Then** no skill annotation appears.
3. **Given** a user wants to understand why a skill fired, **When** they inspect the message's detail/trace view, **Then** they can see the matched skill's name and, at minimum, confirmation that it was applied to that turn.
4. **Given** a user references an active skill via slash-style syntax (`/skill-name`) in their message, **When** Ze responds, **Then** that skill is applied for the turn regardless of whether it would have been matched automatically, and it is visibly annotated the same as an automatically matched skill.
5. **Given** a user explicitly invokes one active skill via `/skill-name` while a different skill would also match automatically, **When** Ze responds, **Then** both skills are applied and both are visibly annotated.

---

### User Story 3 - Manage installed skills (Priority: P2)

A user wants an overview of every skill Ze knows about — which are bundled with Ze itself, which they imported, which are still waiting for review, and which are active or turned off — and wants to act on that list (approve, reject, disable, remove) from one place.

**Why this priority**: Without a management surface, approval and visibility (P1s) still work for a single skill via conversational back-and-forth, but the system becomes unmanageable as the number of imported skills grows. This is necessary for the feature to be usable long-term, but the P1s deliver value on their own first.

**Independent Test**: Can be fully tested by importing multiple skills in different states (pending, active, disabled) and confirming the management view correctly lists, filters, and allows state transitions for each.

**Acceptance Scenarios**:

1. **Given** skills in different states (bundled/active, imported/active, imported/pending review, disabled), **When** the user opens the skills management view, **Then** all skills are listed with their source and current status clearly distinguished.
2. **Given** an active skill the user no longer wants applied, **When** they disable it, **Then** it stops being matched or used in conversation but remains listed (not deleted).
3. **Given** a disabled skill, **When** the user re-enables it, **Then** it resumes being eligible for matching without requiring re-review (its content has not changed since it was last approved).
4. **Given** the user wants to bring in a new skill, **When** they use the "import from URL" action in the management view, **Then** the same fetch/parse/review flow from User Story 1 begins.

---

### User Story 4 - Skill content changes after import (Priority: P3)

A user approved a skill imported from a URL. Later, that URL's content changes (the author updated it) and Ze becomes aware of this on a refresh. Because the user's original approval was of the old content, the changed skill must not silently start acting as if it were still approved.

**Why this priority**: This closes a real trust gap (an approved source could change under the user later), but it is a secondary hardening concern relative to getting import/approval/visibility working, and only matters once skills are already being re-checked over time.

**Independent Test**: Can be fully tested by importing and approving a skill, simulating a change in its source content, triggering a refresh, and confirming the skill reverts to pending-review with the new content shown for re-approval, while the previously-approved version stays inert in the meantime.

**Acceptance Scenarios**:

1. **Given** an active, previously-approved skill whose source content has changed, **When** Ze checks the source again, **Then** the skill's status reverts to pending review and it stops being matched/used until re-approved.
2. **Given** a skill reverted to pending review due to a content change, **When** the user reviews it, **Then** both the previously-approved content and the new content are viewable for comparison.
3. **Given** a skill's source is re-fetched and the content is unchanged, **When** the check completes, **Then** the skill's status and eligibility are unaffected.

---

### Edge Cases

- What happens when an imported skill's name collides with a bundled (developer-authored) skill's name? The system must keep them distinguishable (e.g., by source) rather than letting one silently shadow the other.
- What happens when a skill's declared `allowed-tools` restriction names a tool the relevant agent doesn't have access to in the first place? The restriction has no effect for that tool (a restriction can only narrow existing access, never grant it) — this is not an error.
- What happens when two or more active skills match the same user message? All matched skills used for that turn are surfaced, not just the top one.
- How does the system handle an import source that becomes permanently unreachable (deleted URL, 404) on a later refresh? The last-approved version keeps working; the user is informed the source can no longer be verified, but the skill is not deactivated on that basis alone.
- How does the system handle a skill with an empty or missing description? Rejected at parse time — the description is required for a skill to ever be matchable.
- What happens if a user tries to approve a skill whose instructions attempt to reference or invoke tools directly (prompt content asking the agent to "always call tool X")? This is a prompt-injection risk inherent to any instructions-only skill; the system's mitigation is the review step making that instruction text visible to the user before approval, not automatic detection.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow a user to submit a URL pointing to a skill definition (a `SKILL.md` file, optionally packaged with supporting files) for import.
- **FR-002**: System MUST fetch and parse the submitted source according to the open Agent Skills format (YAML frontmatter including at minimum name and description, plus a free-text instructions body; optional `allowed-tools` list; optional supporting/reference files).
- **FR-003**: System MUST reject import sources that fail to parse (missing required frontmatter fields, unreachable URL, malformed content) with a clear, specific error, and MUST NOT create a skill record from a failed parse.
- **FR-004**: System MUST place every newly imported skill into a "pending review" status and MUST NOT make it eligible for matching or use in any conversation until a user explicitly approves it.
- **FR-005**: System MUST show the user the full parsed content of a pending skill (name, description, complete instructions body, any declared tool restrictions, and any unsupported elements such as bundled executable scripts) before they can approve it.
- **FR-006**: System MUST allow the user to approve a pending skill, transitioning it to active status, or reject it, ensuring it never becomes active in its current form.
- **FR-007**: System MUST support developer-authored skills that ship bundled inside Ze's own domain packages, distinguishing their source ("bundled") from imported skills in every place skills are listed or surfaced.
- **FR-008**: System MUST NOT grant a skill any tool-calling capability beyond what the agent handling the conversation already has. A skill's declared tool restriction (if present) MAY narrow which of the agent's existing tools are exposed while that skill is in use, but MUST NOT expand it.
- **FR-009**: System MUST detect when a parsed skill references bundled executable scripts (a capability defined by the wider Agent Skills format) and MUST flag this plainly to the user during review as unsupported in this phase, rather than silently ignoring or partially applying it.
- **FR-010**: System MUST record, for each conversational turn where one or more active skills were used, which skill(s) were used, in a form retrievable alongside that message's other explainability information.
- **FR-011**: System MUST visibly indicate to the user, on or alongside the assistant's response, when one or more skills were used to produce it, including each skill's name.
- **FR-012**: System MUST provide a management view listing every skill (bundled and imported) together with its source and current status (pending review, active, disabled, rejected).
- **FR-013**: System MUST allow the user to disable an active skill (removing it from matching/use without deleting its record) and re-enable a disabled skill without requiring re-review, provided its approved content has not changed since disabling.
- **FR-014**: System MUST allow the user to permanently remove an imported skill.
- **FR-015**: System MUST re-check an imported skill's source content and, upon detecting any change from the previously-approved version, revert that skill to pending review status and suspend its eligibility for matching/use until re-approved.
- **FR-016**: System MUST retain the previously-approved content of a skill under re-review so the user can compare it against the newly fetched content.
- **FR-017**: System MUST distinguish skills with identical or similar names by their source, so an imported skill can never be confused with or silently override a bundled skill (or another imported skill) of the same name.
- **FR-018**: System MUST require a non-empty name and description on every skill before it can be considered valid for import or bundling; a skill missing either MUST be rejected at parse time.
- **FR-019**: System MUST determine skill applicability during a conversation through two complementary paths: (a) automatic matching, where Ze embeds each active skill's name/description once and compares it against the message's existing routing embedding, applying any skill whose similarity clears a configured relevance floor, always disclosed after the fact per FR-011; and (b) explicit invocation, where a user references a specific active skill via slash-style syntax (`/skill-name`) in their message and that skill MUST be applied for that turn regardless of the automatic relevance match, taking precedence over — and combinable with — any automatically matched skills in the same turn.
- **FR-020**: System MUST apply every active skill uniformly across all agents — a skill is not scoped or assigned to specific agents; once active, it is eligible for matching in any agent's conversation turn.
- **FR-021**: System MUST re-check each imported skill's source content on a daily proactive job cadence (in addition to any user-triggered manual refresh from the management view per FR-015).
- **FR-022**: System MUST fetch and store an imported skill's non-script supporting reference files (e.g. bundled markdown/data files alongside `SKILL.md`) and MUST make their content available to be injected into conversation context when that skill is used, distinct from bundled executable scripts which remain unsupported per FR-009.

### Key Entities *(include if feature involves data)*

- **Skill**: A named, reusable unit of instructions available uniformly across all of Ze's agents (no per-agent scoping). Attributes: name, description, instructions body, source (bundled vs. imported, with imported skills carrying an origin reference such as the import URL), status (pending review, active, disabled, rejected), optional tool-access restriction, non-script supporting reference files (stored content, available for injection into context when the skill is used), indicator of any unsupported elements (e.g. referenced executable scripts) found at parse time, and timestamps for import/approval/last-checked.
- **Skill Review**: The record of a user's decision on a given version of a skill's content — what content was shown, what the user decided (approved/rejected), and when. Needed to support re-review after a content change (User Story 4) without losing the history of prior approvals.
- **Skill Usage**: A record linking a conversational turn to the skill(s) that were matched and applied to it, used to power the visible "skill used" indicator and the turn's explainability/trace information.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can go from having a skill's URL to that skill being active and usable in conversation in under 2 minutes, including the review step.
- **SC-002**: 100% of imported skills are shown to the user for review before ever influencing a conversation — zero instances of an unreviewed skill affecting a response.
- **SC-003**: Every conversational response influenced by a skill carries a visible, correct attribution to that skill; users can identify which skill(s) shaped a given response without needing to ask.
- **SC-004**: When an approved skill's source content changes, 100% of subsequent conversations are shielded from the changed content until the user re-approves it.
- **SC-005**: A user managing 20+ imported skills can find any specific skill's status and act on it (disable/remove/re-review) in under 30 seconds via the management view.

## Assumptions

- Ze remains a single-user personal assistant for the scope of this feature; there is no multi-tenant permission model for who may import or approve skills — the one user of a given Ze instance has full control.
- Import sources are either a direct URL to a `SKILL.md` file or a URL to an archive containing a `SKILL.md` plus supporting reference files, both per the open Agent Skills format's directory layout.
- Re-checking an imported skill's source for content changes (User Story 4) happens via a daily proactive job plus user-triggered manual refresh (FR-021), not via real-time push from the source; sources are not assumed to notify Ze of changes themselves.
- A curated, browsable marketplace/index of skills is out of scope for this phase; only "import a specific known URL" is in scope. The data model should not need to change to add a marketplace later, but no marketplace UI or discovery surface is built now.
- Sandboxed execution of any bundled scripts a skill might reference is out of scope for this phase; such skills are only usable for their instructions content, with the executable portion flagged as unsupported.
- Ze's underlying deployment/execution architecture (currently a deployed API service) does not change as part of this feature.
