# Feature Specification: Trace Telemetry (187b)

**Feature Branch**: `187b-trace-telemetry`

**Created**: 2026-10-18

**Status**: Draft

**Input**: User description: "backend first: the trace fields 187's instruments need, e.g. per-node timings), to run after 187 lands, in parallel with 191 ... gaps taken from 187's instruments" (user, through the Maestro, 2026-10-18). The gaps come from Canvas, the 187 lead, in the floor's Handoffs note (2026-10-18).

**Governed by**: phase 89 (message trace), 95 (streamed partial trace frames), 162/182 (System One judgments and the model tier), 187 (Ask, the trace instruments), 195 (screen trace), `specs/arch/system-one-models.md`.

**Depends on**: 187 on `main` (landed). It runs in parallel with the other web phases. Its web lane touches only 187's trace instruments (`widgets/assemble`).

**Doctrine function served**: governance (honest self-report: the trace shows what Ze measured, not what the client guessed).

**Owning packages** (for planning): ze-core (trace types, the streamed turn, telemetry), ze-api (trace schemas, the partial frame), the generated client, ze-web (the 187 trace instruments). No migration: the trace is already stored as JSON on each message.

## Context

Phase 187 turned each reply's trace into HUD instruments: a signal path through the turn's stages, routing, judgments, model readouts, tools and memory. Several of them draw guesses today, because the trace lacks what they need:

- **Signal path.** Stage times are the client's arrival times, measured against when it sent the message. A reply opened from history has none. Six stages (preprocess, skills, correlate, surface, synthesize, memory write) send no stage frame at all.
- **Turn duration.** The "total" is the sum of tool durations, so the UI labels it "Tool time" and draws no total.
- **Routing.** The trace has the winning agent's confidence and gap, but not the embedding shortlist with scores or the bars the router compared them against.
- **Judgments.** Each System One judgment has its answer and probabilities, but not the bar it was held to or the surface it belongs to.
- **Model readouts.** The trace names the model but has no tokens, cost or context-window fill for the reply.
- **Tools.** Live tool rows report a duration of 0 and success, whatever happened, and have no start time.
- **Memory.** Live memory rows lack the extraction confidence the committed trace carries.

187 already added the tool call's agent and index, extraction confidence on committed memory rows, and compaction and resume-recap flags on the frame.

## Clarifications

### Session 2026-10-18 (user answers through the Maestro: all recommended)

- Q: Does 187b also switch the web instruments to the new fields? → A: Yes. A small web lane drops the client-side guesses (arrival-time offsets, the "Tool time" label, list-position tool keys).
- Q: The current total field (today the sum of tool durations)? → A: Hard-cut rename to `tool_duration_ms`, and add the measured `turn_duration_ms`.
- Q: How is context fill defined? → A: The largest prompt sent to the main model in the turn, divided by that model's window.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The signal path shows real stage times, live and from history (Priority: P1)

While a turn runs, each stage the turn passes through appears with how long the server spent in it. Opening an old reply shows the same stages and times.

**Why this priority**: the signal path is the instrument that explains where a slow reply spent its time. Today it measures the network and the client, and is blank for history.

**Independent Test**: run a turn through a graph with every stage; the live frames and the stored trace list each stage once, in order, with a start offset and a duration from the server's clock; reopening the reply returns the same list.

**Acceptance Scenarios**:

1. **Given** a turn, **When** each stage finishes, **Then** a partial frame carries that stage's name, its start offset from the turn's start, and its duration in milliseconds.
2. **Given** the finished reply, **When** it is fetched later, **Then** its trace holds the same stage list.
3. **Given** a turn that pauses for a confirmation and resumes, **When** it finishes, **Then** the stage list covers both runs, and the wait shows as a gap between them, not inside a stage.
4. **Given** a stage that did not run on this turn (for example, decompose on a single-agent turn), **When** the trace is read, **Then** that stage is absent, not listed with zero time.

---

### User Story 2 - Turn total, model tokens, cost and context fill (Priority: P1)

The trace reports the measured length of the whole turn, and for the reply: tokens in and out for the main model, the estimated cost, and how full the model's context window was.

**Why this priority**: the readouts are a large part of what the user sees for every reply; today two of them are wrong or missing.

**Independent Test**: a turn with one main-model call of known usage reports those tokens, a cost from the price table, the window fill from the window table, and a total at least as long as the sum of its stages.

**Acceptance Scenarios**:

1. **Given** a finished turn, **When** the trace is read, **Then** the total is measured wall time from the turn's start to its reply, separate from tool time. The total includes time spent waiting for a confirmation, and that wait is also reported on its own so the readout can show active time (total minus wait).
2. **Given** a turn with several main-model calls (an agentic loop), **When** the trace is read, **Then** tokens are summed across them, and context fill is the largest prompt sent divided by that model's window.
3. **Given** System One judgments on the turn, **When** the trace is read, **Then** their tokens are reported apart from the main model's, never mixed into them.
4. **Given** a model missing from the price or window table, **When** the trace is read, **Then** the cost and fill are marked as estimates from the default rates, not left blank.

---

### User Story 3 - Routing and judgments show their bars (Priority: P2)

The routing instrument shows the embedding shortlist with each agent's score and the thresholds the router used. Each judgment row names its surface and the bar its answer was held to.

**Why this priority**: an instrument that shows a score without its bar cannot say why Ze decided as it did.

**Independent Test**: an embedding-routed turn's trace lists the shortlisted agents with scores, highest first, plus the threshold and gap bar; a judgment row from a calibrated surface carries the surface name and its bar.

**Acceptance Scenarios**:

1. **Given** an embedding-routed turn, **When** routing finishes, **Then** the partial frame and the trace carry the shortlist (agent, score), the confidence threshold and the gap threshold.
2. **Given** a turn routed another way (screen, preset, forced, open query), **When** the trace is read, **Then** the shortlist is empty and the method says why.
3. **Given** a judgment from a surface with configured bars, **When** the trace is read, **Then** the row names the surface and the bar that decided it, as configured at the time of the turn.
4. **Given** a judgment from a surface with no bars (off or uncalibrated), **When** the trace is read, **Then** the bar is absent and the row says the surface was not calibrated.

---

### User Story 4 - Live tool and memory rows tell the truth (Priority: P2)

A tool row that appears while the turn runs carries its real start offset, duration and success, and the same index as the committed row. Live memory rows carry extraction confidence like committed ones.

**Why this priority**: today the live rows contradict the committed ones a moment later (every tool "succeeds" in 0 ms).

**Independent Test**: a failing tool call shows success false and its measured duration on the live frame, and its live row carries the same call id as its committed row.

**Acceptance Scenarios**:

1. **Given** a tool call, **When** it ends, **Then** the live row carries its start offset from the turn's start, its measured duration, its success, its agent and its call id, all equal to the committed row's values.
2. **Given** a tool call that fails, **When** it ends, **Then** the live row says it failed.
3. **Given** memory retrieved for the turn, **When** the live memory frame goes out, **Then** each fact row carries its extraction confidence.

### Edge Cases

- A turn that errors before it replies still stores the stages and total it reached.
- Work Ze does after the reply is sent (fire-and-forget memory writes) is not part of the turn's stages, total or usage.
- A server restart while a turn waits for a confirmation loses the first run's telemetry; the resumed reply's trace is marked partial and sends no live stage frames.
- A write parked for confirmation shows live as waiting, not as a failed tool; once approved, the row it becomes keeps the same id, so the trace shows one call.
- A slow or displaced client never slows the turn: live frames are sent in the background and dropped if they cannot go out.
- A retried reply (165/180) has its own stage list and totals; the replaced reply keeps its own.
- Clock: all offsets and durations come from one monotonic server clock (the process's), shared by stages and tool rows, so a wall-clock change mid-turn cannot shift or reverse them. Wall time is used only to display when the turn happened.
- A node that runs twice in one turn (a confirmation round re-entering execute) is listed once per run, in order.
- Old traces stored before this phase lack the new fields; they read as absent, and the instruments keep their current fallback.
- A partial frame must never block or fail the turn: a telemetry error is logged and the turn continues.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The trace MUST carry an ordered list of stages, each with name, start offset from the turn's start and duration in milliseconds, measured on the server. It MUST be sent on a partial frame as each stage finishes and stored with the reply.
- **FR-002**: Every graph node a turn passes through MUST be reported as a stage, including preprocess, skill matching, correlate, loop surfacing, synthesize and the memory write. A stage that did not run MUST be absent.
- **FR-003**: The trace MUST carry the measured total duration of the turn, separate from tool time. The existing field that holds the sum of tool durations MUST be renamed to say so (pre-v1 hard cut).
- **FR-004**: The trace MUST carry the main model's prompt and completion tokens summed over chat completions in the turn (transcription and other non-chat usage excluded), the estimated cost from the price table, and the context fill (largest prompt over that model's window), each marked as estimated when the model fell back to default rates or window. System One tokens MUST be reported separately.
- **FR-005**: The routing trace MUST carry the embedding shortlist (agent and score, highest first) and the confidence and gap thresholds in force for the turn, on the partial frame and the stored trace.
- **FR-006**: Each judgment row MUST carry its surface name and the bar that decided it (or none when the surface had no bars), as configured at the time of the turn.
- **FR-007**: Live tool rows MUST carry start offset, measured duration, success, agent and a call id equal to the committed row's (the committed flattened index stays; parallel subtasks finish in any order, so the live and committed rows are matched by id, not by position). Live memory rows MUST carry extraction confidence.
- **FR-008**: Telemetry MUST never fail or delay a turn: errors in measuring or sending are logged and skipped.
- **FR-009**: The REST trace response, the trace frame schema and the generated web client MUST expose the new fields.
- **FR-010**: The web trace instruments MUST read the new fields: the signal path uses server stage offsets (live and from history), the readouts show the measured turn total and the model usage, routing draws the shortlist against its thresholds, judgment rows show their bar, and live tool rows are keyed by call id. The client-side arrival-time offsets and the "Tool time" stand-in MUST be removed.
- **FR-011**: Docs MUST describe the new trace fields (native interface, architecture where the trace is described).

### Key Entities

- **Stage timing**: name, start offset (ms), duration (ms).
- **Turn usage**: main-model prompt and completion tokens, estimated cost, context fill, estimated flag; System One tokens.
- **Routing shortlist**: agent, score; confidence threshold; gap threshold.
- **Judgment bar**: surface, bar name and value, or uncalibrated.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a turn that runs every stage, the stored trace lists every stage the turn ran, and the sum of stage durations is within the total.
- **SC-002**: Reopening any reply recorded after this phase shows the same stage times it showed live (no difference).
- **SC-003**: Live tool rows and committed rows agree on call id, duration and success for 100% of calls in the test suite.
- **SC-004**: Measuring adds under 5 ms to a turn's median server time in the turn tests.
- **SC-005**: The Python suites, the web suites, the web typecheck and lint pass.
- **SC-006**: No web instrument computes a stage offset from client arrival time (a test fails if it does).

## Assumptions

- The stage list names graph nodes as the graph defines them; the web app maps them to the signal path's labels.
- Cost is an estimate from the existing static price table (the same table the spend budget uses); reconciled cost from the provider stays in Usage.
- No migration: traces are stored as JSON, and old traces simply lack the fields.
