# Contract: the loop-inflow commit and the commit decision

Research R6–R8, R10. Owned by lane `inflow`; the types in `decision.py` are part of the contract step (lane `lead`, T002).

## `ze_worldstate/decision.py`

```python
CommitKind = Literal["resolve", "create_declared", "create_suspected", "hold", "fallback"]
GateKind = Literal["resolve", "create_suspected", "hold", "fallback"]

@dataclass(frozen=True)
class CommitDecision:
    kind: CommitKind
    reason: str
    consumed: frozenset[str] = frozenset()
    title: str | None = None        # 109 gate only
    window_days: int | None = None  # 109 gate only

CommitOutcome = Literal["created", "matched", "resolved", "no_match", "no_title", "held", "dismissed", "error"]

@dataclass(frozen=True)
class CommitResult:
    outcome: CommitOutcome
    reason: str
    loops: tuple[OpenLoop, ...] = ()
```

Producers:

| Producer | Returns | Kinds it can produce |
|---|---|---|
| `loop_judge.decide(result, cfg, provenance)` | `CommitDecision` | `GateKind` (never `create_declared`) |
| `commitment_judge.decide(...)` | `IntakeOutcome`; its three loop kinds are `CommitKind` strings | `resolve`, `create_declared`, `create_suspected` (plus the intake's own kinds) |
| `extraction.decide_with_109_gate(text, llm_client, model)` | `CommitDecision` with `title` and `window_days` | `resolve`, `create_declared`, `create_suspected`, `hold` |

## `LoopInflow` (`admission.py`)

```python
class LoopInflow:
    def __init__(self, *, lifecycle, loop_store, graph_store, entity_resolver, llm_client,
                 embedder, system_one_client=None, settings=None,
                 model=DEFAULT_EXTRACTION_MODEL) -> None: ...

    async def extract(self, text, provenance, evidence=(), source_ref=None) -> None:
        """Email, calendar, ingestion: judge (202's surface call), log, then self.commit(...)."""

    def finish(self, text, provenance, decision: CommitDecision, *, judgment=None,
               source: SourceKey | None = None) -> LoopAdmission:
        """Builds the full record; attaches nothing callable. 202 owns `judgment=`."""

    async def commit(self, decision: CommitDecision, *, text: str, inflow: str,
                     evidence: Sequence[EvidenceRef] = (),
                     source: SourceKey | None = None) -> CommitResult:
        """The one commit path. Never raises."""
```

`memory_store`, `collision_store` and `nli_client` leave `LoopInflow`: they belong to `LoopLifecycle` now (the contribution seam runs inside the create events).

### `commit` decision table

| Decision | Steps | Result |
|---|---|---|
| `hold` | none | `held` |
| `fallback` | `decide_with_109_gate`; continue with its decision | as below |
| any, no title, writer returns nothing | — | `no_title`, nothing written |
| `resolve` | entities → match a live loop → `lifecycle.resolve` | `resolved` / `no_match` |
| `create_suspected` | entities → dropped match with the same fingerprint? → live match? → `lifecycle.create_suspected` | `dismissed` / `matched` / `created` |
| `create_declared` | entities → live match? → `lifecycle.create_declared(window_days=decision.window_days or the writer's)` | `matched` / `created` |
| any exception | log `loop_commit_failed` once | `error` |

On a live match: not suspected → `lifecycle.note_evidence`; suspected → `Corroborator.on_suspected_match` (research R10).

Provenance on create: `create_declared` from the conversation inflow stores `user_declared` (as today); other inflows store the inflow name.

## `Corroborator` (`corroboration.py`)

```python
class Corroborator:
    def __init__(self, *, lifecycle, loop_store, system_one_client=None, settings=None) -> None: ...
    async def on_suspected_match(self, existing: OpenLoop, dropped: OpenLoop | None,
                                 match: MatchInput) -> SourceWrite | OpenLoop:
        """Never raises; on any error it falls back to lifecycle.note_evidence."""

@dataclass(frozen=True)
class MatchInput:
    text: str
    inflow: str
    key: SourceKey | None
    evidence: tuple[EvidenceRef, ...]
    entity_ids: tuple[UUID, ...]
```

202's `_judge` and the surface-config block move into this class unchanged. `is_independent` and `corroborated_confidence` stay pure module functions.

## `CommitmentIntake` (`intake.py`)

- `loop_inflow` read-only property (for the container, research R8).
- `_apply`: `elif outcome.kind in LOOP_COMMIT_KINDS: admission.loop = self._inflow.finish(prompt, CONVERSATION, CommitDecision(outcome.kind, outcome.reason, outcome.consumed), source=source)`.
- `_fallback`: `CommitDecision("fallback", reason)`.
- `_link_one`: `await self._lifecycle.link(loop.id, **{f"{kind}_id": target})`. The intake takes `lifecycle` in its constructor.
- `_LOOP_KIND` and the `admission.source = …` mutation are deleted.

## `write_memory` (`ze_core/orchestration/nodes/memory.py`, the loop-commit hunk only)

```python
loop_commit = config["configurable"].get("loop_commit")
if loop_result is not None and loop_commit is not None and loop_result.decision.kind != "hold":
    fire_and_forget(_commit_with_episode(loop_commit, loop_result, episode_task), label="loop_commit")

async def _commit_with_episode(commit, admission, episode_task):
    ...  # await the episode, then
    return await commit(admission.decision, text=admission.text, inflow=admission.inflow,
                        evidence=refs, source=admission.source)
```

The container sets `configurable["loop_commit"] = self.commitment_intake.loop_inflow.commit` (`apps/ze-api/ze_api/wiring/container.py`, beside `commitment_intake`).

## Trace and calibration (spec Clarifications 2026-10-26)

- The `intake_outcome` row's answer carries the new kind strings.
- `apps/ze-web/src/widgets/assemble/lib/instruments/judgments.ts` maps `resolve`, `create_declared`, `create_suspected` to the same three sentences; `judgments.test.ts` rows change with it.
- `eval/calibration/commitment_intake.py` (`CREATES`, `WRITES`, the `outcome.kind ==` comparisons at lines 105-106, 335-336 and 879) reads the new strings. Only the kind literals change (agreed with 202). `eval/calibration/loop_gate.py` and `commitment_intake_baseline.py` already use `create_declared` / `create_suspected` and read `decide(...).kind`, so they should need no change; the lane confirms it with `make calibrate-loop-gate ARGS=--check-sets` and `make calibrate-commitment-intake ARGS=--check-sets` (offline).
