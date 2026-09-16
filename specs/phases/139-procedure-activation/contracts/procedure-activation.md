# Contract: Governed Procedure Activation

This contract consumes the public Phase-138 lifecycle contract. Names are implementation guidance; semantics are normative.

## Discovery

```python
class ProcedureDiscovery(Protocol):
    async def match(
        self,
        context: ProcedureTaskContext,
        *,
        agent_allowed_tools: frozenset[str],
        capability_allowed_tools: frozenset[str],
    ) -> list[ProcedureMatch]: ...
```

`ProcedureTaskContext` contains the caller identity, task/planning text, available structured context, and existing trace/task references. It must not introduce a separate copy of a user session.

`ProcedureMatch` includes the immutable `procedure_id` and version/revision, state (`ready`, `blocked`, `not_relevant`), matching rationale, satisfied/unmet preconditions, steps, and `effective_tool_names`.

Eligibility precedes matching: only a Phase-138 validated, enabled, current version can be actionable. A relevant version with unmet required preconditions is `blocked`; it cannot be invoked.

## Invocation

```python
class ProcedureActivator(Protocol):
    async def invoke(
        self,
        match: ProcedureMatch,
        *,
        origin: ProcedureInvocationOrigin,
    ) -> ProcedureInvocation: ...

    async def record_action(
        self,
        invocation_id: UUID,
        *,
        step_ref: str,
        action_trace_ref: UUID | str | None,
        capability_decision: CapabilityDecision,
        outcome: ProcedureActionOutcome,
    ) -> ProcedureActionLink: ...

    async def complete(
        self,
        invocation_id: UUID,
        *,
        outcome: ProcedureOutcome,
        summary: str,
    ) -> ProcedureOutcomeFeedback: ...
```

`invoke` accepts only a `ready` match and rechecks lifecycle eligibility before creating a record. It is called only after an agent or planner explicitly selects a match. Discovery alone never calls it.

For each guided action:

```text
effective tools = agent-authorized tools
                ∩ capability-permitted tools
                ∩ procedure-relevant tool hints
```

The capability gate remains the execution authority. An empty intersection blocks that step; it must not fall back to a larger set.

## Feedback

`complete` is idempotent per terminal invocation. It emits structured feedback to the Phase-138 review/confidence intake and returns the recorded feedback. It must not directly alter lifecycle status, approval, disablement, or confidence.

## Management REST surface

All routes sit under `/api/v0/`, declare response models, summaries, descriptions, and the existing API-key dependency.

| Method and path | Purpose |
|---|---|
| `GET /api/v0/procedures` | List current procedures with lifecycle status, confidence, trigger, version, and last activation outcome; supports status/search filters. |
| `GET /api/v0/procedures/{procedure_id}` | Return current detail plus immutable version summary, preconditions, steps, and activation summary. |
| `GET /api/v0/procedures/{procedure_id}/versions/{version}` | Return one historical/current version, source evidence, and outcomes/traces. |
| `PATCH /api/v0/procedures/{procedure_id}` | Submit a governed edit; response reports the Phase-138 revision/review result. |
| `POST /api/v0/procedures/{procedure_id}/disable` | Disable immediately through Phase 138. |

The management surface does not add a direct approval endpoint. If Phase 138 already exposes review endpoints, the UI links or composes those authoritative operations rather than duplicating them.

## Trace response extension

Procedure-guided action trace data includes:

```json
{
  "procedure": {
    "invocation_id": "uuid",
    "procedure_id": "uuid",
    "version": 3,
    "step_ref": "step-2",
    "capability_decision": "allowed",
    "outcome": "succeeded"
  }
}
```

The field is absent for ordinary actions. A historical trace must resolve its referenced procedure version after later edits or disablement.

## Errors

- Invalid lifecycle eligibility, blocked preconditions, missing explicit invocation, and stale version selection use typed domain errors.
- A capability denial is represented as a traced denied action, not converted into procedure approval.
- Unknown procedure/version returns the existing typed not-found/API mapping.

## Forbidden behavior

- Automatic execution on match.
- Invocation of unreviewed, rejected, superseded, or disabled versions.
- Tool grants or capability bypasses.
- Direct confidence/lifecycle mutations from activation feedback.
- New `signal_sources()` wiring or contribution arbitration.
