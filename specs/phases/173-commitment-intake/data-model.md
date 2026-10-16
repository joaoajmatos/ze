# Data Model: One Commitment Intake

## Migration `zw004` (ze-worldstate chain, after `zw003`)

```sql
ALTER TABLE open_loops ADD COLUMN reminder_id UUID NULL;
```

No foreign key (reminders belong to ze-calendar). `goal_id` already exists. Downgrade drops the column.

## Types

- `OpenLoop` (`ze_worldstate/types.py`): add `reminder_id: UUID | None = None`.
- `TurnCreation` (`ze_agents/nested_tools.py`, frozen dataclass): `reminder_id: str | None`, `goal_id: str | None`.
- `CommitmentIntakeSurfaceConfig` (`ze_worldstate/commitment_judge.py`): `enabled`, `choice_hold`, `family_hold`, `biography_hold`, `loop_hold`, `explicit_hold`, `resolves_hold`; `calibrated` = enabled and all six bars set.
- `IntakeOutcome` kinds: `persist_fact`, `resolve_loop`, `create_loop_declared`, `create_loop_suspected`, `link`, `hold`, `fallback`; fields `reason`, `consumed`, `link_kind` (`reminder` | `goal`).
- `IntakeAdmission`: `fact: FactAdmission | None`, `loop: LoopAdmission | None`, `links: tuple[LinkOutcome, ...]` (one per kind the turn created; a turn that created a reminder and a goal links both; `LinkOutcome` = `kind`, `linked`), `judgment`, `question_kinds`, `consumed`, `skip_reason`.
- `SpeechAct` (`ze_memory/types.py`) shrinks to `FACT, FORGET, INGEST, CLARIFY, NONE`.

## Store

`LoopStore.link(loop_id, *, reminder_id=None, goal_id=None) -> bool`: one UPDATE, `SET reminder_id = COALESCE(reminder_id, $2), goal_id = COALESCE(goal_id, $3) WHERE id = $1 AND state IN ('suspected','active','drifting')`. Returns whether a row changed. `_row_to_loop` and `create` carry `reminder_id`.

## REST

`LoopListItem` and loop detail schema (`ze_api/api/schemas.py`): `reminder_id: str | None`, `goal_id: str | None`.

## Config

`system_one.surfaces.commitment_intake` replaces `speech_act`; `loop_gate` stays for email, calendar and ingestion. Ships off, null bars.
