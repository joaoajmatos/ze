# Feature Specification: Session Context Continuity

**Feature Branch**: `112-session-context-continuity`

**Created**: 2026-08-10

**Status**: Implemented

**Input**: User description: "In-session context management for Ze: (1) mid-session context compaction — a new graph node that keeps recent turns verbatim and folds older conversation history into a rolling summary once token usage crosses a threshold, replacing the currently unbounded AgentState.messages growth per thread; requires a per-model context-window table (OpenRouter routed models) and a new compaction-focused summarization prompt distinct from ze-memory's existing archival session-summary prompt; (2) a structured resume brief injected at session-boundary (large gap since last_active_at) that recaps the thread using Ze's existing structured state — latest SessionSummariser narrative, active OpenLoops via the existing surface_loops/matching machinery, in-flight goals/workflows due soon — rather than re-summarizing raw chat text. Explicitly out of scope: LangGraph checkpoint branching/time-travel (not needed, compaction is an in-place update_state on the same thread lineage)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Long conversations never break (Priority: P1)

As the user, I keep a single conversation thread going for weeks — the same thread
accumulates hundreds of turns as I ask Ze about calendar, email, goals, and general
questions. Today that thread's history grows without bound; eventually it will exceed
what the underlying model can accept, causing the assistant to fail or silently
degrade mid-conversation. I need the conversation to keep working indefinitely,
without me having to start a new thread to "reset" it, and without noticing any
drop in the assistant's ability to recall what we discussed.

**Why this priority**: This is the reliability floor. Without it, long-running
threads eventually break outright — a hard failure, not a degraded experience.

**Independent Test**: Can be fully tested by driving a single thread through enough
turns to exceed the routed model's context budget and confirming the assistant keeps
responding correctly, still grounded in earlier decisions, without erroring.

**Acceptance Scenarios**:

1. **Given** a thread whose accumulated conversation history is approaching the
   routed model's context capacity, **When** the user sends the next message,
   **Then** the system compacts older turns into a rolling summary before calling
   the model, keeps the most recent turns intact, and the turn completes normally.
2. **Given** a thread that has already been compacted once, **When** the
   conversation continues to grow, **Then** the system compacts again as needed
   (compaction is repeatable, not a one-time event per thread).
3. **Given** a compacted thread, **When** the user asks about a decision or fact
   established well before the compaction point, **Then** the assistant's response
   still reflects that decision or fact correctly.

---

### User Story 2 - Picking a conversation back up (Priority: P2)

As the user, I often step away from Ze for hours or days and come back to the same
thread. Today I have to re-explain what's still open — pending goals, outstanding
questions, things Ze was tracking. I want Ze to already know what was left
unresolved when I return, the way a competent assistant would after being away,
instead of treating my return as a blank slate or, conversely, blindly re-reading
raw chat transcript back at me.

**Why this priority**: This is the experience that makes long-lived threads feel
continuous rather than disposable — but it's additive on top of P1's reliability
guarantee, not required for the thread to keep functioning.

**Independent Test**: Can be fully tested by letting a thread sit idle past the
resume threshold, then sending a new message and confirming the assistant's
response reflects outstanding open loops, goals, or workflows that existed before
the gap — without the user having to restate them.

**Acceptance Scenarios**:

1. **Given** a thread with no activity for longer than the resume threshold and at
   least one active open loop, in-flight goal, or in-flight workflow tied to it,
   **When** the user sends a new message, **Then** the assistant's handling of that
   turn is informed by those outstanding items without the user mentioning them,
   surfaced only through the content of the assistant's reply — not as a
   separate "welcome back" message of its own.
2. **Given** a thread with no activity for longer than the resume threshold but
   nothing outstanding (no open loops, goals, or workflows), **When** the user
   sends a new message, **Then** the turn proceeds normally with no irrelevant or
   fabricated recap content.
3. **Given** a thread with a gap shorter than the resume threshold, **When** the
   user sends a new message, **Then** no resume brief is assembled — this is a
   session-boundary behavior, not a per-turn one.

---

### User Story 3 - Trusting what was kept vs. summarized (Priority: P3)

As the user, when I ask "what did we actually decide about X," I want a way to
tell whether the assistant's answer is grounded in my exact words or in a
compacted summary of them, so I can judge how much to trust a recollection from
far back in a long thread.

**Why this priority**: Nice-to-have transparency on top of P1/P2 — the thread
still works and still resumes coherently without it, but trust in long-running
memory improves if compaction isn't a silent, invisible process.

**Independent Test**: Can be fully tested by triggering compaction on a thread,
then inspecting that turn's explainability trace and confirming it indicates
which parts of the conversation were passed verbatim versus folded into a
summary.

**Acceptance Scenarios**:

1. **Given** a turn whose prompt included a rolling summary, **When** the user
   inspects that message's trace, **Then** the trace indicates a summary was
   present and roughly what span of the conversation it covers.

---

### Edge Cases

- What happens when compaction itself needs to run but the model call that
  produces the summary fails (e.g., LLM error, timeout)? The turn must not be
  lost — the system should fall back to a safe behavior (e.g., hard-trim to the
  verbatim window and proceed) rather than blocking the user's message.
- What happens when the routed model for a turn has no known context-window
  entry (a new or unlisted OpenRouter model)? The system must not crash; it
  should fall back to a conservative default budget.
- What happens when a session resumes but the underlying open loops, goals, or
  workflows it would have referenced were closed or dropped during the gap? The
  resume brief must reflect current state, not stale state from before the gap.
- What happens when the user's very first message to a brand-new thread arrives?
  There is no prior activity, so no resume brief and no compaction should apply.
- What happens when compaction and a resume brief would both apply to the same
  turn (a long-idle thread whose history also exceeds the context budget)? Both
  behaviors should compose without conflicting — the resume brief augments
  context, compaction shrinks it; order of application must not lose the resume
  brief itself to compaction.
- What happens to a conversation's full, uncompacted history from a data
  standpoint — is it still visible anywhere (e.g., message history / memory
  feed) after in-session compaction has shrunk what's sent to the model? Yes —
  compaction only affects what's sent to the model for a turn; the stored
  message record is never truncated or overwritten by it (see Clarifications).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST track, per conversation thread, whether the
  accumulated conversation history has crossed 70% of the context capacity of
  the model handling that thread's turns. This conservative margin leaves
  headroom for token growth that happens later in the same turn (agentic
  tool-loop outputs, memory context) after the pre-turn check has run.
- **FR-002**: When a thread's conversation history crosses that 70% threshold,
  the system MUST reduce what is sent to the model by keeping a window of the
  most recent turns intact and replacing older turns with a condensed summary,
  before the turn is processed.
- **FR-003**: The condensed summary MUST preserve decisions made, constraints
  established, outstanding tasks, and outcomes of prior actions — not just a
  narrative recap of topics discussed.
- **FR-003a**: Compaction MUST NOT alter, truncate, or discard the stored,
  permanent record of the conversation — it only changes what is sent to the
  model for a given turn. The full original text of every past turn MUST
  remain retrievable through Ze's existing message history / memory surfaces.
- **FR-004**: Compaction MUST be repeatable — a thread that keeps growing after
  being compacted once MUST be compacted again as needed, without manual
  intervention.
- **FR-005**: The system MUST maintain a way to estimate context capacity per
  model the assistant can be routed to, and MUST have a defined fallback budget
  for models without a known capacity.
- **FR-006**: The system MUST detect when a thread resumes after a period of
  inactivity exceeding a defined threshold. This threshold MUST be the same
  shared inactivity value Ze's existing session-narrative summarization
  already uses — not a second, independently configured value — to avoid two
  competing definitions of "session boundary."
- **FR-007**: On a detected resume, the system MUST assemble a recap from the
  thread's existing tracked state — the latest available session narrative
  summary, currently active open loops relevant to the thread, and in-flight
  goals or workflows relevant to the thread — rather than re-summarizing raw
  conversation text.
- **FR-007a**: The resume recap MUST be applied as silent priming context for
  the assistant's next response only. It MUST NOT be surfaced to the user as
  its own visible message (e.g., no standalone "welcome back" banner or chat
  bubble) — it may only be reflected indirectly, through the content of the
  assistant's own next reply.
- **FR-008**: The resume recap MUST be omitted or empty when there is nothing
  outstanding for the thread, without fabricating content.
- **FR-009**: The resume recap MUST NOT be assembled for turns that don't cross
  the inactivity threshold — this is a session-boundary behavior only.
- **FR-010**: If compaction fails to produce a summary (e.g., the summarization
  call errors), the system MUST fall back to a safe reduction of the
  conversation history rather than failing the user's turn.
- **FR-011**: The system MUST record, per turn, whether that turn's context
  included a compacted summary and/or a resume recap, in a form inspectable via
  Ze's existing per-message explainability trace.
- **FR-012**: Compaction and resume-recap assembly MUST both be able to apply to
  the same turn without either one discarding the other.

### Key Entities *(include if feature involves data)*

- **Conversation Thread**: An ongoing, uniquely identified conversation between
  the user and Ze; the unit compaction and resume behavior apply to.
- **Rolling Summary**: The condensed representation of a thread's older
  conversation turns, replacing them in what's sent to the model while the
  verbatim recent-turn window is kept intact.
- **Context Budget**: The estimated capacity, per model the assistant can be
  routed to, used to decide when a thread's history needs compaction. A
  thread's history is considered to need compaction once it crosses 70% of
  this budget.
- **Resume Recap**: The structured, assembled-not-summarized brief presented to
  the assistant only (silent priming, never its own visible user-facing
  message) when a thread resumes after a period of inactivity, built from the
  thread's existing outstanding state (session narrative, open loops, goals,
  workflows).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A single conversation thread can sustain at least 500 turns of
  ordinary use without the assistant failing to respond due to context-capacity
  errors.
- **SC-002**: A scripted eval suite of recall scenarios (facts/decisions
  established more than 50 turns earlier, in threads compacted at least once)
  achieves at least 90% correct-recall accuracy, measured through Ze's
  existing eval framework.
- **SC-003**: In at least 90% of sessions resumed after the inactivity threshold
  with outstanding open loops, goals, or workflows, the assistant's first
  response reflects that outstanding state without the user having to restate
  it.
- **SC-004**: Compaction adds no perceptible delay to the turn that triggers it
  beyond Ze's normal response-time expectations for a turn involving an extra
  LLM call.
- **SC-005**: Zero threads fail a turn outright due to exceeding model context
  capacity after this feature ships, for any model Ze can route to (known or
  unknown to the context-budget table).

## Assumptions

- A conversation thread (`thread_id`) is the unit of session boundary; each
  thread is compacted and resumed independently of any other concurrent thread.
- The inactivity threshold that triggers a resume recap is the same value Ze's
  existing session-narrative summarization already uses (see FR-006) — a
  single shared config knob, not a second, independently tuned threshold.
- Compaction operates only on what is sent to the model for a turn; it never
  mutates or truncates the stored message record, and it does not change the
  retention policy of Ze's separate long-term memory record (facts, episodes),
  which stays governed by existing memory consolidation behavior.
- The resume recap draws only from state Ze already tracks (session summaries,
  open loops, goals, workflows); it does not require inventing new tracked
  state or asking the user new profiling questions.
- Models Ze can route to but does not yet have a known context capacity for are
  handled with a conservative fallback rather than blocking routing to them.

## Clarifications

### Session 2026-08-10

- Q: After in-session compaction shrinks what's sent to the model, does the
  full, uncompacted original conversation need to stay retrievable elsewhere
  (e.g., scrolling chat history / memory feed), or is it acceptable for detail
  folded into a rolling summary to no longer be recoverable in full fidelity? →
  A: The original conversation text stays fully retrievable elsewhere (e.g.
  message history). Compaction only shapes what is sent to the model for a
  turn — it never discards or overwrites the stored record of what was
  actually said.
- Q: Should the resume recap be shown to the user directly (e.g., a visible
  "here's what's outstanding" message when they return), or should it only
  silently inform the assistant's next response without being surfaced as its
  own message? → A: Silent priming only. The resume recap shapes the
  assistant's next response but is never presented as its own visible message.

### Session 2026-08-10 (clarify pass)

- Q: What percentage of the routed model's context capacity should trigger
  compaction? → A: 70% — conservative, to leave headroom for token growth that
  happens later in the same turn (agentic tool-loop outputs, memory context)
  after the pre-turn compaction check has already run.
- Q: Should the resume-recap inactivity threshold be a separate, independently
  configurable value from the existing session-narrative-summary inactivity
  window, or the same shared value? → A: Same shared value — a second,
  independently-tuned threshold would be a confusing second definition of
  "session boundary." One config knob governs both.
- Q: How should SC-002's recall-correctness claim be quantified so it's
  testable and repeatable? → A: Absolute target via Ze's existing eval
  framework — at least 90% correct-recall accuracy on a scripted eval suite —
  rather than a relative "as often as before" baseline comparison.
