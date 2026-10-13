# Contract: Loop evidence, corroboration and grounding

## Signatures

```python
# ze_memory/store.py (Protocol) and ze_memory/retriever.py (impl)
async def write_episode(self, session_id: str, agent: str, prompt: str,
                        response: str, embedding: Any) -> UUID | None: ...
```
Returns `row["id"]` on success; `None` after the existing logged failure path. Callers that ignore the result are unchanged.

```python
# ze_worldstate/types.py
@dataclass
class LoopAdmission:
    ...
    commit: Callable[[Sequence[EvidenceRef]], Awaitable[list[OpenLoop]]] | None = None

# ze_worldstate/admission.py
async def extract(self, text: str, provenance: str,
                  evidence: Sequence[EvidenceRef] = ()) -> None: ...
def _commit_for(...) -> Callable[[Sequence[EvidenceRef]], Awaitable[list[OpenLoop]]]: ...
```
`_commit_for` passes `evidence_refs=list(evidence)` to `propose_loop_candidates`. `LoopInflow.admit` is unchanged.

```python
# ze_worldstate/inflow.py
make_loop_extractor_from_parts(...) -> Callable[..., Awaitable[None]]   # (text, provenance, evidence=()) 
```

## Conversation (`write_memory`)

```python
episode_task = fire_and_forget(store.write_episode(...), label="write_episode")
...
if loop_result.commit is not None:
    fire_and_forget(_commit_with_episode(loop_result.commit, episode_task), label="loop_commit")

async def _commit_with_episode(commit, episode_task):
    episode_id = None
    try:
        episode_id = await episode_task
    except Exception:
        pass                                   # already logged by fire_and_forget
    refs = [EvidenceRef(kind="episode", id=episode_id)] if episode_id else []
    return await commit(refs)
```

`EvidenceRef` is imported in `ze_core` from `ze_plugin.contribution` (ze-core already depends on ze-plugin). The node never imports `ze_worldstate`. The reply path never awaits `episode_task`.

## Email, ingestion, calendar

| Caller | Code |
|---|---|
| `InboundMessageProcessor` (messenger) | `episode_id = await self._memory.write_episode(...)`; `refs = [EvidenceRef("episode", episode_id)] if episode_id else []`; `self.loop_extractor(msg.body, "email", evidence=refs)`. `EvidenceRef` from `ze_sdk.contribution` |
| `MemorySink.push` (ingestion) | pass the `evidence` list it already builds (`[EvidenceRef("ingestion", ingest_uuid)]` or `[]`) |
| `CalendarReminderJob` | no change; logs `calendar_loop_no_evidence` at debug once per call |

The extractor attribute type becomes `Callable[..., Awaitable[None]] | None` in the three owners. A test double with the old two-argument shape fails loudly (TypeError), which is intended: update the double.

## Declared path

`_create_declared_loop` gains `graph_store`, `embedder`, `memory_store` parameters and, before creating:

```python
existing = await find_matching_loop(entity_ids, title, loop_store=..., graph_store=...,
                                    embedder=..., states=["suspected","active","drifting"])
if existing is not None:
    await _link_evidence_and_entities(existing.id, evidence_refs, entity_ids, loop_store)
    if evidence_refs and existing.state is LoopState.ACTIVE:
        await loop_store.record_corroboration(existing.id)
    return existing
```
When `graph_store is None` the dedup step is skipped (as for the suspected path). The create call passes `check_fact_exists` and `check_episode_exists` built by one helper `_existence_checkers(memory_store)` shared with `_create_suspected_loop`.

The three declared call sites (`USER_DECLARED` direct, `_commit_admitted`, the Haiku fallback gate) go through the same function, so dedup applies to all.

## Suspected path, matched branch

```python
if existing is not None:
    await _link_evidence_and_entities(existing.id, evidence_refs, entity_ids, loop_store)
    if evidence_refs and existing.state is LoopState.ACTIVE:
        await loop_store.record_corroboration(existing.id)
    return [existing]
```

## Grounding

```python
# LoopSurfacer.passes_push_bar
evidence_labels = await self._evidence_labels(loop.id)
if not await passes_grounding(loop.title, evidence_labels, nli_client, grounding_threshold):
    return False
```
(was `rationale`). Novelty keeps `rationale`. With no labels the check still passes (an evidence-less loop, e.g. from calendar).

`_fetch_evidence_summaries` episode query:

```sql
SELECT COALESCE(summary,
                CASE WHEN agent = 'messenger'
                     THEN prompt || ' ' || left(response, 500)
                     ELSE prompt END) AS s
FROM memory_episodes WHERE id = $1
```

## Dismissal semantics (FR-014)

Unchanged code. `drop_loop` stores `compute_evidence_fingerprint(list_evidence(loop))`. `_create_suspected_loop` suppresses when a `dropped` match has `dismissed_evidence_fingerprint == compute_evidence_fingerprint(new_refs)`. Documented behavior:

| Dropped loop evidence | New call evidence | Result |
|---|---|---|
| `{episode A}` | `{episode A}` | suppressed |
| `{episode A}` | `{episode B}` | new `suspected` loop |
| none | none | suppressed |
| none | `{episode B}` | new `suspected` loop |

## Test matrix

- Unit (`ze-worldstate/tests/test_admission.py`, `test_extraction.py`): commit receives and links refs; declared path dedups; declared path passes checkers; fingerprint table above; `record_corroboration` called only for active matches with new refs.
- Unit (`ze-core/tests/orchestration/test_loop_admission_node.py`): commit receives the episode ref; a failed episode task yields `[]`; the node returns before the episode task finishes.
- Unit (`ze-messenger`, `ze-ingestion`, `ze-calendar` tests): extractor called with `evidence=`; calendar without.
- Unit (`ze-memory`): `write_episode` returns the id (mock pool `fetchrow`).
- Unit (`test_surfacing.py`): grounding is called with the title.
- PG (`tests/pg/test_loop_evidence.py`): create via the real inflow commit with an episode row present; evidence listed; `_fetch_evidence_summaries` returns the email body text for a messenger episode; push bar with an NLI stub (low for rationale, high for title) passes.
