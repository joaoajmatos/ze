# Feature Specification: One Scheduler

**Feature Branch**: `213-one-scheduler`

**Created**: 2026-10-22

**Status**: Draft

**Depends on**: 204

**Input**: Architecture review 2026-10-22, candidate C11. One scheduler module in ze-proactive handles cron and one-shot jobs, with catch-up and run records. The `WorkflowScheduler` keeps only workflow-run bookkeeping. The engine stops reaching into ze-automation, and the calendar's one-shot jobs migrate.

## Context *(verified against the code, 2026-10-22)*

Two APScheduler loops run in one process:

- **`ProactiveScheduler`** (`ze_proactive/scheduler.py`, 187 lines) has cron only (`add_cron_job`, :73). It records every run (`_recording`, :100) for `proactive_job_runs`, and on start it schedules catch-ups with `missed_fire_time` (`_schedule_catch_ups`, :143-160).
- **`WorkflowScheduler`** (`ze_automation/workflow/scheduler.py`, 304 lines) has its own `AsyncIOScheduler` (:62) and its own workflow catch-up (`_catch_up`, :108-132). It also has generic engine-wide methods:
  - `schedule_job(fn, cron, job_id)` (:190)
  - `schedule_at(fn, dt, job_id, args)` (:201)
  - `remove_job_if_exists(job_id)` (:212)

Callers of the generic methods:

- **The engine.** `ze_core/bootstrap.py:280-300` takes `workflow_scheduler: Any` and schedules `cost_reconciliation` (every 15 min) and `checkpoint_pruning` (hourly) on it. These jobs leave no `proactive_job_runs` row, get no catch-up, and are missing from `GET /api/v0/proactive/job-runs`. The engine depends on a ze-automation object that its declared dependencies hide.
- **ze-calendar one-shots:**
  - `agents/reminders/tools.py:61,124` (user reminders)
  - `reminders/calendar.py:163,218,250` (event reminders)
  - `plugin.py:152,190` (startup)
- **The calendar's own late-reminder replay:** `replay_unsent` (`reminders/calendar.py:152-169`), which fires with `late_from`.

That makes three catch-up mechanisms: proactive job runs, workflow executions, and the calendar replay.

Plugins also schedule cron jobs in two ways: through `register_proactive_jobs`, and inside `startup()` through `container.proactive_scheduler` (news, finance, calendar). The plugin-seam phase (210) owns that second path. This phase only gives both paths one scheduler to call.

**Blast radius** (`graphify affected`):

- `ProactiveScheduler`: `ze_api/wiring/{container,jobs}.py`, the bootstraps of ze-automation, ze-correlation, ze-memory and ze-proactive, `ze_sdk/proactive.py`, and `ze_messenger/plugin.py`.
- `WorkflowScheduler`: ze-automation (`__init__`, the workflow agent and its seven tools, `bootstrap.py`, `workflow/runner.py`), plus `ze_core/bootstrap.py` and ze-calendar (reminders agent and tools, plugin, `reminders/calendar.py`) through the generic methods.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ze's own maintenance shows up in Governance and catches up after downtime (Priority: P1)

Cost reconciliation and checkpoint pruning appear in the job-runs list with their last run. A run missed while Ze was down catches up under the same policy as every other job.

**Why this priority**: today these two jobs are invisible and never catch up. Spend accuracy depends on cost reconciliation.

**Independent Test**: start the scheduler with a fake run store whose last cost reconciliation was 3 hours ago, and assert one catch-up run and a recorded run row.

**Acceptance Scenarios**:

1. **Given** Ze was stopped for 2 hours, **When** it starts, **Then** cost reconciliation runs once as a catch-up, and a run row is recorded.
2. **Given** the job-runs list in Governance, **When** the user opens it, **Then** `cost_reconciliation` and `checkpoint_pruning` are listed.

---

### User Story 2 - A reminder set in chat fires once, even across a restart (Priority: P1)

User and event reminders are one-shot jobs on the one scheduler. A reminder due while Ze was down fires once on startup, marked late, through the scheduler's one-shot catch-up, not through a calendar-only replay.

**Why this priority**: reminders are requested pushes. A missed or doubled reminder is the most visible failure of scheduling.

**Independent Test**: schedule a one-shot for 10:00, simulate a restart at 10:05, and assert one late fire with the late wording. Restart again and assert no second fire.

**Acceptance Scenarios**:

1. **Given** a reminder due at 10:00 and Ze down from 09:55 to 10:05, **When** Ze starts, **Then** the reminder fires once, labelled late.
2. **Given** the user cancels a reminder, **When** its time comes, **Then** nothing fires and nothing is left in the scheduler.
3. **Given** a reminder older than its catch-up age limit, **When** Ze starts, **Then** it is recorded as missed and not fired.

---

### User Story 3 - Workflows keep their schedule and catch-up (Priority: P2)

Scheduled workflows run on the shared scheduler. The workflow module keeps only run bookkeeping: stale recovery, cancellation, the running set and held-write cancellation.

**Independent Test**: add, update and remove a scheduled workflow through the workflow tools, and assert that the shared scheduler holds exactly the expected jobs and that a missed fire catches up once.

**Acceptance Scenarios**:

1. **Given** a workflow scheduled hourly and a missed fire during downtime, **When** Ze starts, **Then** one catch-up run starts. This matches the behaviour the old `_catch_up` gave.

### Edge Cases

- **Job id collisions across owners** (`reminder:<id>` vs `user_reminder:<id>` vs a workflow id). Ids are namespaced by owner, and a duplicate id is an error.
- **A one-shot in the past at schedule time** fires immediately, or is refused, by one rule.
- **Timezones.** Cron and one-shot times use the user's timezone, as the proactive scheduler does today.
- **Shutdown during a run.** The run record ends as interrupted, not succeeded.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST have exactly one scheduling module, in ze-proactive. It offers cron jobs, one-shot jobs and job removal, and records every run with start, end and outcome.
- **FR-002**: Catch-up after downtime MUST be one policy for cron and one-shot jobs alike, with a per-job maximum age, using the existing `missed_fire_time` rule.
- **FR-003**: The engine's maintenance jobs (cost reconciliation, checkpoint pruning) MUST register with the one scheduler. ze-core MUST NOT receive a workflow scheduler.
- **FR-004**: The workflow module MUST keep only workflow-run bookkeeping. Its cron jobs are registered with the one scheduler, and its own `AsyncIOScheduler` and `_catch_up` are deleted.
- **FR-005**: ze-calendar's user and event reminders MUST be one-shot jobs on the one scheduler. `replay_unsent`'s late-fire behaviour is kept as the one-shot catch-up, including the "late, was due HH:MM" wording.
- **FR-006**: Plugins MUST reach the one scheduler only through the SDK's proactive surface, not through a container attribute named for a workflow concept.
- **FR-007**: Job ids MUST be namespaced by owner, and a duplicate registration MUST fail loudly.
- **FR-008**: The job-runs read route MUST list every job the scheduler runs, including one-shot outcomes for at least the last run per job id prefix. The plan decides the retention.
- **FR-009**: Pre-v1 hard cut. `schedule_job`, `schedule_at` and `remove_job_if_exists` leave `WorkflowScheduler`, and all callers move in the same phase.

### Key Entities

- **Scheduled job**: a named unit of work with a cron or one-shot trigger, an owner and a catch-up policy.
- **Job run**: one execution of a scheduled job, with its start, end and outcome.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: One scheduler loop runs in the process, so a grep finds exactly one `AsyncIOScheduler(` in non-test code.
- **SC-002**: Every scheduled job, including the engine's maintenance and reminders, has a run record after it runs.
- **SC-003**: Across a simulated restart, a due reminder fires exactly once, and a reminder past its catch-up age never fires.
- **SC-004**: `ze_core` has no parameter or attribute that holds a workflow scheduler.

## Assumptions

- Phase 204 has landed, so jobs no longer read the push log for cooldowns. This keeps the job bodies that move here small.
- APScheduler stays the timer underneath. This phase changes owners, not the library.
- The `proactive_job_runs` table can hold one-shot runs, or gains a narrow companion table. The plan decides.
- Plugin `startup()` scheduling is cleaned up by phase 210. This phase only makes sure both paths reach one scheduler.
