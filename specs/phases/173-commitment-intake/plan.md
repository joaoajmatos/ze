# Implementation Plan: One Commitment Intake

**Branch**: `173-commitment-intake` | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md)

## Summary

Replace the conversation speech-act request (163) and the conversation loop-gate request (168) with one request: the `commitment` Choice plus the fact questions (`family`, `biography`) and the loop Nouls (`is_open_concern`, `explicit_declaration`, `resolves_existing`). One pure `decide()` merges them and reads what the turn already created (reminder or goal tool calls). A `link` outcome writes `reminder_id` / `goal_id` on a matching loop (migration `zw004`). Calibrate on new EN+PT sets. Show the links as chips on `/loops`.

## Technical Context

Python 3.12, asyncpg, Alembic raw SQL, pytest `asyncio_mode=auto`. React + Vite, FSD, vitest. System One via `SystemOneClient` (162). No new third-party dependency.

## Decisions

**D-1 Owner of the merged judge: `ze-worldstate`.** `ze-worldstate` already depends on `ze-memory`, so the new `ze_worldstate/commitment_judge.py` (questions, state, config, `decide`) and `ze_worldstate/intake.py` (`CommitmentIntake`) can import the fact helpers; the reverse would add a cycle. The fact questions (`family`, `biography`) and the Haiku value writer stay in `ze-memory`: `speech_act_judge.py` is renamed `fact_judge.py` and keeps only the fact questions, `build_state` and `decide_fact()` (the 163 persist/hold rules, taking an already-read Choice). No plugin imports either (plugins reach memory only through `ze_sdk`; nothing changes for them).

**D-2 One call from `write_memory`.** `write_memory` gets `config["configurable"]["commitment_intake"]` (wired in `ze_api/container.py`) in place of the `asyncio.gather` of `fact_extractor` and `loop_admission`. `CommitmentIntake.admit(configurable, prompt, response, agent, tool_calls)` returns an `IntakeAdmission` (fact result, loop admission with commit, link outcome, judgment rows). On `fallback` it delegates internally to `gather_fact_proposals`' Haiku path and `LoopInflow`'s 109 Haiku fallback, so the node stays small. When `commitment_intake` is absent (a ze-core container without worldstate) `write_memory` runs `fact_extractor` alone, as today without a loop gate. `LoopInflow.admit` (conversation) is deleted; `LoopInflow.extract` (email, calendar, ingestion) stays on the `loop_gate` surface, unchanged.

**D-3 Reading the turn.** `ze_agents/nested_tools.py` gets `turn_creation(tool_calls) -> TurnCreation`, next to `tracking_earned`. It flattens nested calls and counts `set_reminder` and `create_goal` only when `call.success` is true and the payload has an `id` and no `error` (both tools already return `{"id": ...}`). No tool module is edited, so floor 181's metadata changes do not collide; if 181 changes what `success` means for a gated or confirmation-held call, `turn_creation` follows it (task T020 re-reads 181's diff).

**D-4 Linking.** `CommitmentIntake` on `link` resolves entities from the user message with the existing `entity_resolver`, calls `find_matching_loop(entity_ids, prompt[:200], states=[suspected, active, drifting])`, and calls the new `LoopStore.link()` (set-once `COALESCE`). No loop is created. No match means nothing happens (logged).

**D-5 Label hard cut.** `SpeechAct` shrinks to `FACT, FORGET, INGEST, CLARIFY, NONE`. `admit_speech_act` maps unknown to `NONE`; the Haiku fallback prompt and `_admit_parsed` use the same set (C2). `reminder`, `loop`, `goal`, `drop` are deleted from `ze_memory.types`, `ze_sdk/memory.py`, tests and fixtures. `forget`, `ingest`, `clarify` are named non-fact classes (spec R2): `decide()` holds each with its own reason on the trace (decision table row 9), and the Haiku fallback reads each through `admit_speech_act` and admits no fact. Two tests pin FR-016 (a)-(d): `test_commitment_labels.py` in ze-worldstate for the Choice side (ze-memory cannot import `decide()`), `test_speech_act_labels.py` in ze-memory for the fallback side.

**D-6 Calibration baseline.** The old two-surface pipeline is deleted from product code (hard cut), so `eval/calibration/commitment_intake_baseline.py` holds a frozen copy of the 163 questions and `decide` and uses `loop_judge.decide` (still live for other inflows) to replay the baseline on the same rows. Frozen copy lives under `eval/` only.

**D-7 Config.** `speech_act` block deleted, `commitment_intake` block added (off, null bars). `loop_gate` stays. After a held-out `ENABLE`, the block is turned on in a separate calibration task (needs the user's OK for spend).

**D-8 Which doctrine functions.** Executive (open-loop state). Perception facts keep their seam licences unchanged. No new claim kind.

## Constitution / pre-v1 check

Hard cuts only: no shim for the removed labels, no dual surface after enable. The `loop_gate` surface remains because three inflows still need it; that is a scope boundary, not a shim.

## Shared files with floor 181 (Keystone)

| File | Risk | Handling |
|---|---|---|
| `core/engine/ze-core/ze_core/orchestration/nodes/memory.py` | both floors may edit | keep our diff to the `gather` block (~lines 125-160); rebase on whichever lands first |
| `core/contracts/ze-agents/ze_agents/nested_tools.py` | 181 may add helpers | we add one function and one dataclass at the end of the "earned" helpers |
| `ToolCall` / `call_tool` (`ze_agents/types.py`, `tool.py`) | semantics of `success` / `gate` | read only; T020 re-reads 181's diff |
| `plugins/ze-calendar/.../reminders/tools.py`, `ze_automation/agents/goals/tools.py` | tool metadata | not edited here; return shape `{"id": ...}` is relied on |

## Source layout (touched)

```text
core/cognition/ze-memory/ze_memory/{types.py,extractor.py,speech_act_judge.py -> fact_judge.py,__init__.py}
core/cognition/ze-worldstate/ze_worldstate/{commitment_judge.py,intake.py,admission.py,store.py,types.py,matching.py(read),migrations/versions/zw004_loop_reminder_link.py}
core/contracts/ze-agents/ze_agents/nested_tools.py
core/engine/ze-core/ze_core/orchestration/nodes/memory.py, ze_core/container.py
packages/ze-sdk/ze_sdk/memory.py
apps/ze-api/{ze_api/container.py,ze_api/api/routes/loops.py,ze_api/api/schemas.py,config/config.yaml}
apps/ze-web/src/{entities/loop,widgets/loop-review}
packages/ze-client (generated via make codegen)
eval/calibration/{commitment_intake.py,commitment_intake_baseline.py,commitment_intake.jsonl,commitment_intake_holdout.jsonl}; eval/calibration/{speech_act.py,speech_act.jsonl} removed
Makefile (calibrate-commitment-intake replaces calibrate-speech-act)
docs/*, AGENTS.md, specs index, specs/arch/{system-one-models,executive-function}.md
```

## Risks

- Re-calibration cost: one tuned run plus one held-out run; spend needs user OK after the held-out set is committed.
- Mixed-act messages get one label (follow-up).
- `link` depends on the tool result carrying an id; goal creation returns `id` today. Missing id: skip and log.
- `nodes/memory.py` conflict with 181.
