# ze-correlation

Correlation engine for Ze — cross-domain hypothesis formation from the memory graph, with neighbourhood expansion and signal pinning.

## Role in Ze

Ze's memory graph connects facts, episodes, contacts, news signals, and calendar events. The correlation engine traverses this graph to surface non-obvious connections — "this news article relates to your goal about Rust" — and can push high-salience hypotheses proactively.

### Key features

- `CorrelationEngine` — LLM-driven hypothesis formation from graph seeds
- Graph neighbourhood expansion with configurable hop limits and recall guarantees
- `PostgresHypothesisStore` — persists hypotheses with evidence references
- Proactive push delivery for high-salience correlations (discretionary, shared budget, via ntfy)
- Inline correlation during conversation turns (the `correlate` graph node in `ze-core`)
- `HypothesisDecayJob` — decays hypothesis confidence over time

### Integration

The `correlate` graph node in `ze-core` runs inline correlation after `execute_tool`. `CorrelationJob` runs on a schedule from `ze-api`. Plugins contribute signal sources via `ZePlugin.signal_sources()` — news and calendar plugins feed the engine.

`screen_resolvers.py` registers the `hypothesis` screen resolver. A hypothesis line says it is an inference.

## Responsibilities

| Module | What it provides |
|---|---|
| `engine.py` | `CorrelationEngine` — forms hypotheses from graph signals |
| `store.py` | `PostgresHypothesisStore` — hypothesis persistence |
| `job.py` | `CorrelationJob` — scheduled correlation runs |
| `push.py` | `CorrelationPushConsumer` — delivers correlation insights as discretionary pushes |
| `prompts.py` | LLM prompt templates for hypothesis generation |
| `types.py` | `Hypothesis`, `HypothesisEvidence` |
| `rest.py` | `list_hypotheses`, `set_feedback` — the REST query surface |
| `bootstrap.py` | `build_correlation_stack`, `register_proactive_jobs` |
| `push_kinds.py` | The `hypothesis` `PushKind` (discretionary) |
| `screen_resolvers.py` | The `hypothesis` screen resolver |
| `jobs/hypothesis_decay.py` | `HypothesisDecayJob` |

## Dependencies

![ze-correlation package dependencies](../../docs/diagrams/core/cognition/ze-correlation/dependencies.svg)

<sub>[Interactive version](../../docs/diagrams/core/cognition/ze-correlation/dependencies.html)</sub>

Third-party: `asyncpg`.

Migrations: branch `zcor` — `zcor001` creates `correlation_hypothesis`, `zcor002` adds the claim kind, and `zcor003` adds `confirmed` and `promoted_at`.

## Usage

Wired into the orchestration graph by `ze-core` (`orchestration/nodes/correlation.py`) and started as a proactive job from `ze-api`:

```python
from ze_correlation import CorrelationEngine, PostgresHypothesisStore
```

## REST (phase 185)

`ze_correlation.rest` lists hypotheses (`GET /api/v0/hypotheses`, filtered by entity and state: open, confirmed, dismissed, all) and records feedback (`POST /api/v0/hypotheses/{id}/feedback`: `useful`, `not_relevant`, `muted`, or `null` to clear). A `not_relevant` or `muted` hypothesis is no longer pushed, ranked, or offered by `who_is_on_project`. `SocialCooccurrenceJob` still sees it (`include_dismissed=True`) so it keeps updating the evidence. A confirmed hypothesis lists as confirmed whatever its feedback.

## Testing

From the repo root:

```bash
make test-correlation
```

See [docs/testing.md](../../docs/testing.md).
